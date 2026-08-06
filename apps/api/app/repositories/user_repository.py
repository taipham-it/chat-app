import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))

    async def get_by_username(self, username: str) -> User | None:
        return await self.session.scalar(
            select(User).where(func.lower(User.username) == username.strip().lower())
        )

    async def search(self, query: str, *, current_user_id: uuid.UUID, limit: int = 20) -> list[User]:
        pattern = f"%{query.strip().lower()}%"
        result = await self.session.scalars(
            select(User)
            .where(
                User.id != current_user_id,
                User.is_active.is_(True),
                or_(func.lower(User.username).like(pattern), func.lower(User.email).like(pattern)),
            )
            .order_by(User.username)
            .limit(limit)
        )
        return list(result)

    async def create(self, *, email: str, username: str, password_hash: str) -> User:
        user = User(email=email, username=username, password_hash=password_hash)
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

