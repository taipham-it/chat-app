import asyncio
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.models.user import User
from app.repositories.user_repository import UserRepository

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def build_google_authorization_url(state: str, redirect_uri: str | None = None) -> str:
    settings = get_settings()
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(
        {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": redirect_uri or settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid profile email",
            "state": state,
            "prompt": "select_account",
        }
    )


def _fetch_google_identity(code: str, redirect_uri: str | None = None) -> dict[str, object]:
    settings = get_settings()
    token_request = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=urllib.parse.urlencode(
            {
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri or settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            }
        ).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(token_request, timeout=10) as response:  # noqa: S310
            token_data = json.load(response)
        access_token = token_data.get("access_token")
        if not access_token:
            raise AuthenticationError("Google did not return an access token.", code="GOOGLE_TOKEN_ERROR")
        user_request = urllib.request.Request(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with urllib.request.urlopen(user_request, timeout=10) as response:  # noqa: S310
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AuthenticationError("Google sign-in could not be completed.", code="GOOGLE_AUTH_FAILED") from exc


async def fetch_google_identity(code: str, redirect_uri: str | None = None) -> dict[str, object]:
    return await asyncio.to_thread(_fetch_google_identity, code, redirect_uri)


class GoogleAuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def get_or_create_user(self, identity: dict[str, object]) -> User:
        email = str(identity.get("email", "")).strip().lower()
        if not email or identity.get("email_verified") is not True:
            raise AuthenticationError(
                "Google account email is not verified.", code="GOOGLE_EMAIL_UNVERIFIED"
            )
        existing = await self.users.get_by_email(email)
        if existing:
            if not existing.is_active:
                raise AuthenticationError("This account is inactive.", code="ACCOUNT_INACTIVE")
            return existing

        base = re.sub(r"[^a-z0-9_.-]", "", email.split("@", 1)[0])[:40]
        if len(base) < 3:
            base = f"user_{base}"[:40]
        username = base
        suffix = 1
        while await self.users.get_by_username(username):
            suffix += 1
            username = f"{base[: 49 - len(str(suffix))]}_{suffix}"

        user = User(email=email, username=username, password_hash="!google-oauth")
        self.session.add(user)
        try:
            await self.session.commit()
            await self.session.refresh(user)
            return user
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.users.get_by_email(email)
            if existing:
                return existing
            raise AuthenticationError(
                "Could not create the Google account.", code="GOOGLE_ACCOUNT_ERROR"
            ) from exc
