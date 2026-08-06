import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.models.conversation import Conversation
from app.models.conversation_member import ConversationMember
from app.models.message import Message
from app.models.message_reaction import MessageReaction
from app.models.user import User


class MessageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def require_membership(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> ConversationMember:
        member = await self.session.get(ConversationMember, (conversation_id, user_id))
        if not member:
            raise AuthorizationError(
                "You are not a member of this conversation.",
                code="CONVERSATION_ACCESS_DENIED",
            )
        return member

    async def send_text_message(
        self,
        *,
        current_user: User,
        conversation_id: uuid.UUID,
        client_message_id: uuid.UUID,
        content: str,
    ) -> Message:
        content = content.strip()
        if not content:
            raise ValidationError("Message cannot be empty.", code="EMPTY_MESSAGE")
        if len(content) > 10_000:
            raise ValidationError("Message is too long.", code="MESSAGE_TOO_LONG")
        await self.require_membership(conversation_id, current_user.id)
        conversation = await self.session.get(Conversation, conversation_id)
        if not conversation:
            raise NotFoundError("Conversation not found.", code="CONVERSATION_NOT_FOUND")
        existing = await self.session.scalar(
            select(Message).where(
                Message.sender_id == current_user.id,
                Message.client_message_id == client_message_id,
            )
        )
        if existing:
            return existing
        message = Message(
            conversation_id=conversation_id,
            sender_id=current_user.id,
            client_message_id=client_message_id,
            type="text",
            content=content,
            status="sent",
        )
        conversation.updated_at = datetime.now(UTC)
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def find_by_client_id(self, *, sender_id: uuid.UUID, client_message_id: uuid.UUID) -> Message | None:
        return await self.session.scalar(
            select(Message).where(
                Message.sender_id == sender_id,
                Message.client_message_id == client_message_id,
            )
        )

    async def send_media_message(
        self,
        *,
        current_user: User,
        conversation_id: uuid.UUID,
        client_message_id: uuid.UUID,
        media_type: str,
        object_key: str,
        filename: str,
        content_type: str,
        size: int,
    ) -> Message:
        await self.require_membership(conversation_id, current_user.id)
        conversation = await self.session.get(Conversation, conversation_id)
        if not conversation:
            raise NotFoundError("Conversation not found.", code="CONVERSATION_NOT_FOUND")
        existing = await self.find_by_client_id(
            sender_id=current_user.id, client_message_id=client_message_id
        )
        if existing:
            return existing
        message = Message(
            conversation_id=conversation_id,
            sender_id=current_user.id,
            client_message_id=client_message_id,
            type=media_type,
            content=filename,
            media_object_key=object_key,
            media_filename=filename,
            media_content_type=content_type,
            media_size=size,
            status="sent",
        )
        conversation.updated_at = datetime.now(UTC)
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def toggle_reaction(
        self,
        *,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
        emoji: str,
    ) -> Message:
        emoji = emoji.strip()
        if not emoji or len(emoji) > 32:
            raise ValidationError("Invalid reaction emoji.", code="INVALID_EMOJI")
        await self.require_membership(conversation_id, user_id)
        message = await self.session.get(Message, message_id)
        if not message or message.conversation_id != conversation_id:
            raise NotFoundError("Message not found.", code="MESSAGE_NOT_FOUND")

        existing = await self.session.scalar(
            select(MessageReaction).where(
                MessageReaction.message_id == message_id,
                MessageReaction.user_id == user_id,
                MessageReaction.emoji == emoji,
            )
        )

        if existing:
            await self.session.delete(existing)
        else:
            reaction = MessageReaction(
                message_id=message_id,
                user_id=user_id,
                emoji=emoji,
            )
            self.session.add(reaction)

        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def mark_read(self, *, conversation_id: uuid.UUID, user_id: uuid.UUID) -> None:
        member = await self.require_membership(conversation_id, user_id)
        latest_message_id = await self.session.scalar(
            select(Message.id)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
        )
        if latest_message_id and member.last_read_message_id != latest_message_id:
            member.last_read_message_id = latest_message_id
            await self.session.commit()
