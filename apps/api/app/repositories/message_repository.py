import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_messages(
        self,
        *,
        conversation_id: uuid.UUID,
        before_created_at: datetime | None,
        before_id: uuid.UUID | None,
        limit: int,
    ) -> list[Message]:
        query = select(Message).where(Message.conversation_id == conversation_id)
        if before_created_at:
            cursor = Message.created_at < before_created_at
            if before_id:
                cursor = or_(
                    cursor,
                    and_(Message.created_at == before_created_at, Message.id < before_id),
                )
            query = query.where(cursor)
        result = await self.session.scalars(
            query.order_by(Message.created_at.desc(), Message.id.desc()).limit(min(max(limit, 1), 100))
        )
        return list(reversed(list(result)))

