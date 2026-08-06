import re

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError, ValidationError
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register(self, *, email: str, username: str, password: str) -> User:
        email = email.strip().lower()
        username = username.strip().lower()
        if await self.users.get_by_email(email):
            raise ConflictError("A user with this email already exists.", code="USER_EMAIL_EXISTS")
        if await self.users.get_by_username(username):
            raise ConflictError("This username is already taken.", code="USERNAME_EXISTS")
        if not (
            len(password) >= 8
            and re.search(r"[a-z]", password)
            and re.search(r"[A-Z]", password)
            and re.search(r"\d", password)
        ):
            raise ValidationError(
                "Password must contain upper and lowercase letters and a number.",
                code="WEAK_PASSWORD",
            )
        try:
            user = await self.users.create(
                email=email, username=username, password_hash=hash_password(password)
            )
            await self.session.commit()
            return user
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Email or username already exists.", code="USER_EXISTS") from exc

    async def login(self, *, identifier: str, password: str) -> dict[str, str]:
        identifier = identifier.strip().lower()
        user = (
            await self.users.get_by_email(identifier)
            if "@" in identifier
            else await self.users.get_by_username(identifier)
        )
        if not user or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password.", code="INVALID_CREDENTIALS")
        if not user.is_active:
            raise AuthenticationError("This account is inactive.", code="ACCOUNT_INACTIVE")
        subject = str(user.id)
        return {
            "access_token": create_access_token(subject),
            "refresh_token": create_refresh_token(subject),
            "token_type": "bearer",
        }
