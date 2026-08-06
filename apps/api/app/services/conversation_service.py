import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.conversation import Conversation
from app.models.conversation_member import ConversationMember
from app.models.message import Message
from app.models.user import User


def build_direct_key(user_a_id: uuid.UUID, user_b_id: uuid.UUID) -> str:
    first, second = sorted([str(user_a_id), str(user_b_id)])
    return f"direct:{first}:{second}"


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_direct_conversation(
        self, *, current_user: User, target_user_id: uuid.UUID
    ) -> Conversation:
        if current_user.id == target_user_id:
            raise ValidationError("You cannot message yourself.", code="SELF_CONVERSATION")
        target = await self.session.get(User, target_user_id)
        if not target or not target.is_active:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")
        direct_key = build_direct_key(current_user.id, target_user_id)
        existing = await self._get_by_direct_key(direct_key)
        if existing:
            return existing
        conversation = Conversation(
            type="direct", creator_id=current_user.id, direct_key=direct_key
        )
        conversation.members = [
            ConversationMember(user_id=current_user.id, role="owner"),
            ConversationMember(user_id=target_user_id, role="member"),
        ]
        self.session.add(conversation)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self._get_by_direct_key(direct_key)
            if existing:
                return existing
            raise ConflictError("Could not create conversation.") from exc
        return (await self._get_by_direct_key(direct_key)) or conversation

    async def _get_by_direct_key(self, key: str) -> Conversation | None:
        return await self.session.scalar(
            select(Conversation)
            .where(Conversation.direct_key == key)
            .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
        )

    async def list_for_user(self, user_id: uuid.UUID) -> list[Conversation]:
        result = await self.session.scalars(
            select(Conversation)
            .join(ConversationMember)
            .where(ConversationMember.user_id == user_id)
            .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
            .order_by(Conversation.updated_at.desc())
        )
        conversations = list(result.unique())
        conversation_ids = [conversation.id for conversation in conversations]
        if not conversation_ids:
            return conversations

        ranked_messages = (
            select(
                Message,
                func.row_number()
                .over(
                    partition_by=Message.conversation_id,
                    order_by=(Message.created_at.desc(), Message.id.desc()),
                )
                .label("message_rank"),
            )
            .where(Message.conversation_id.in_(conversation_ids))
            .subquery()
        )
        latest_message = aliased(Message, ranked_messages)
        latest_result = await self.session.scalars(
            select(latest_message).where(ranked_messages.c.message_rank == 1)
        )
        latest_by_conversation = {
            message.conversation_id: message for message in latest_result
        }

        read_message = aliased(Message)
        unread_result = await self.session.execute(
            select(Message.conversation_id, func.count(Message.id))
            .join(
                ConversationMember,
                and_(
                    ConversationMember.conversation_id == Message.conversation_id,
                    ConversationMember.user_id == user_id,
                ),
            )
            .outerjoin(read_message, read_message.id == ConversationMember.last_read_message_id)
            .where(
                Message.conversation_id.in_(conversation_ids),
                Message.sender_id != user_id,
                or_(
                    ConversationMember.last_read_message_id.is_(None),
                    Message.created_at > read_message.created_at,
                    and_(
                        Message.created_at == read_message.created_at,
                        Message.id > read_message.id,
                    ),
                ),
            )
            .group_by(Message.conversation_id)
        )
        unread_by_conversation = dict(unread_result.all())

        for conversation in conversations:
            conversation.last_message = latest_by_conversation.get(conversation.id)
            conversation.unread_count = unread_by_conversation.get(conversation.id, 0)
        return conversations
