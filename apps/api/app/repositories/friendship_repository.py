import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.friendship import Friendship
from app.models.user import User


def canonical_pair(first_id: uuid.UUID, second_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (first_id, second_id) if str(first_id) < str(second_id) else (second_id, first_id)


class FriendshipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_between(self, first_id: uuid.UUID, second_id: uuid.UUID) -> Friendship | None:
        low_id, high_id = canonical_pair(first_id, second_id)
        return await self.session.scalar(
            select(Friendship).where(
                Friendship.user_low_id == low_id, Friendship.user_high_id == high_id
            )
        )

    async def get_by_id(self, friendship_id: uuid.UUID) -> Friendship | None:
        return await self.session.get(Friendship, friendship_id)

    async def list_for_user(self, user_id: uuid.UUID, *, status: str) -> list[tuple[Friendship, User]]:
        other_id = or_(
            and_(Friendship.user_low_id == user_id, User.id == Friendship.user_high_id),
            and_(Friendship.user_high_id == user_id, User.id == Friendship.user_low_id),
        )
        rows = await self.session.execute(
            select(Friendship, User)
            .join(User, other_id)
            .where(Friendship.status == status, User.is_active.is_(True))
            .order_by(User.username)
        )
        return list(rows.tuples())

    async def create(self, requester_id: uuid.UUID, recipient_id: uuid.UUID) -> Friendship:
        low_id, high_id = canonical_pair(requester_id, recipient_id)
        friendship = Friendship(
            user_low_id=low_id,
            user_high_id=high_id,
            requested_by_id=requester_id,
            status="pending",
        )
        self.session.add(friendship)
        await self.session.flush()
        await self.session.refresh(friendship)
        return friendship
