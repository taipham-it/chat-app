import secrets
import urllib.parse
import uuid

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.db.session import get_db_session
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    GoogleAuthorizationResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.services.google_auth_service import (
    GoogleAuthService,
    build_google_authorization_url,
    fetch_google_identity,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def google_login_redirect(error: str | None = None) -> str:
    settings = get_settings()
    if not error:
        return f"{settings.FRONTEND_URL.rstrip('/')}/chat"
    return f"{settings.FRONTEND_URL.rstrip('/')}/login?{urllib.parse.urlencode({'error': error})}"


def request_callback_uri(request: Request) -> str:
    """Return the exact callback URI registered with Google."""
    del request
    return get_settings().GOOGLE_REDIRECT_URI


def request_frontend_url(request: Request) -> str:
    settings = get_settings()
    host = request.headers.get("host", request.url.netloc)
    if host.startswith("localhost:8000") or host.startswith("127.0.0.1:8000"):
        return f"{request.url.scheme}://{host.rsplit(':', 1)[0]}:3000"
    return settings.FRONTEND_URL.rstrip("/")


def request_is_secure(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    scheme = forwarded_proto.split(",", 1)[0].strip() if forwarded_proto else request.url.scheme
    return scheme == "https"


def request_cookie_samesite(request: Request | None = None) -> str:
    settings = get_settings()
    if request is None:
        return settings.COOKIE_SAMESITE
    origin = request.headers.get("origin")
    origin_host = urllib.parse.urlparse(origin).hostname if origin else settings.frontend_hostname
    request_host = request.url.hostname
    if origin_host and request_host and origin_host != request_host and request_is_secure(request):
        return "none"
    return settings.COOKIE_SAMESITE


def set_google_oauth_state_cookie(response: Response, request: Request, state: str) -> None:
    response.set_cookie(
        "google_oauth_state",
        state,
        max_age=600,
        httponly=True,
        secure=request_is_secure(request),
        samesite=request_cookie_samesite(request),
        path="/",
    )


def set_auth_cookies(
    response: Response, tokens: dict[str, str], request: Request | None = None
) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    cookie_options = {
        "httponly": True,
        "secure": settings.COOKIE_SECURE if request is None else request_is_secure(request),
        "samesite": request_cookie_samesite(request),
    }
    response.set_cookie(
        "access_token",
        tokens["access_token"],
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        **cookie_options,
    )
    response.set_cookie(
        "refresh_token",
        tokens["refresh_token"],
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/v1/auth",
        **cookie_options,
    )


def clear_auth_cookies(response: Response, request: Request | None = None) -> None:
    settings = get_settings()
    cookie_options = {
        "httponly": True,
        "secure": settings.COOKIE_SECURE if request is None else request_is_secure(request),
        "samesite": request_cookie_samesite(request),
    }
    response.delete_cookie("access_token", path="/", **cookie_options)
    response.delete_cookie("refresh_token", path="/api/v1/auth", **cookie_options)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest, session: AsyncSession = Depends(get_db_session)
) -> UserResponse:
    return UserResponse.model_validate(
        await AuthService(session).register(
            email=str(payload.email), username=payload.username, password=payload.password
        )
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    tokens = await AuthService(session).login(
        identifier=payload.email,
        password=payload.password,
    )
    set_auth_cookies(response, tokens, request)
    return TokenResponse()


@router.get("/google/login")
async def google_login(request: Request) -> RedirectResponse:
    settings = get_settings()
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return RedirectResponse(google_login_redirect("google_not_configured"))
    callback = urllib.parse.urlparse(settings.GOOGLE_REDIRECT_URI)
    loopback_hosts = {"localhost", "127.0.0.1", "0.0.0.0"}
    if (
        request.url.hostname in loopback_hosts
        and callback.hostname in loopback_hosts
        and request.url.hostname != callback.hostname
    ):
        canonical_login_url = urllib.parse.urlunparse(
            (
                callback.scheme,
                callback.netloc,
                f"{settings.API_V1_PREFIX.rstrip('/')}/auth/google/login",
                "",
                "",
                "",
            )
        )
        return RedirectResponse(canonical_login_url)
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(build_google_authorization_url(state, request_callback_uri(request)))
    set_google_oauth_state_cookie(response, request, state)
    return response


@router.get("/google/authorization", response_model=GoogleAuthorizationResponse)
async def google_authorization(request: Request, response: Response) -> GoogleAuthorizationResponse:
    """Return Google's URL without navigating a browser through an ngrok interstitial."""
    settings = get_settings()
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise AuthenticationError("Google sign-in is not configured.", code="GOOGLE_NOT_CONFIGURED")
    state = secrets.token_urlsafe(32)
    set_google_oauth_state_cookie(response, request, state)
    return GoogleAuthorizationResponse(
        authorization_url=build_google_authorization_url(state, request_callback_uri(request))
    )


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    google_oauth_state: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    if error:
        return RedirectResponse(f"{request_frontend_url(request)}/login?error=google_access_denied")
    if not code or not state or not google_oauth_state or not secrets.compare_digest(state, google_oauth_state):
        return RedirectResponse(f"{request_frontend_url(request)}/login?error=google_invalid_state")
    try:
        identity = await fetch_google_identity(code, request_callback_uri(request))
        user = await GoogleAuthService(session).get_or_create_user(identity)
    except AuthenticationError:
        return RedirectResponse(f"{request_frontend_url(request)}/login?error=google_auth_failed")

    response = RedirectResponse(f"{request_frontend_url(request)}/chat")
    set_auth_cookies(
        response,
        {
            "access_token": create_access_token(str(user.id)),
            "refresh_token": create_refresh_token(str(user.id)),
        },
        request,
    )
    response.delete_cookie(
        "google_oauth_state", path="/"
    )
    return response


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    refresh_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    token = refresh_token or (payload.refresh_token if payload else None)
    if not token:
        raise AuthenticationError("Refresh token is missing.", code="REFRESH_TOKEN_MISSING")
    claims = decode_token(token, expected_type="refresh")
    try:
        user_id = uuid.UUID(claims["sub"])
    except (ValueError, TypeError) as exc:
        raise AuthenticationError("Invalid token subject.", code="INVALID_TOKEN") from exc
    user = await UserRepository(session).get_by_id(user_id)
    if not user or not user.is_active:
        raise AuthenticationError("Account is unavailable.", code="ACCOUNT_UNAVAILABLE")
    tokens = {
        "access_token": create_access_token(str(user.id)),
        "refresh_token": create_refresh_token(str(user.id)),
    }
    set_auth_cookies(response, tokens, request)
    return TokenResponse()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response) -> Response:
    clear_auth_cookies(response, request)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
