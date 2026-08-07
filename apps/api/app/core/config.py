import urllib.parse
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Messenger App API"
    APP_ENV: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str
    REDIS_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15   
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    CORS_ORIGINS: str = "http://localhost:3000"
    CORS_ORIGIN_REGEX: str | None = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
    MAX_UPLOAD_SIZE_MB: int = 10
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "messenger_minio"
    MINIO_SECRET_KEY: str = "messenger_minio_password"
    MINIO_BUCKET: str = "messenger-media"
    MINIO_SECURE: bool = False
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    FRONTEND_URL: str = "http://localhost:3000"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma4:latest"
    OLLAMA_TIMEOUT_SECONDS: float = 120.0

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug(cls, value: object) -> object:
        # Some shells expose DEBUG=release; treat that conventional value as false.
        if isinstance(value, str) and value.lower() in {"release", "production", "prod"}:
            return False
        return value

    @field_validator("COOKIE_SAMESITE", mode="before")
    @classmethod
    def normalize_cookie_samesite(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"lax", "strict", "none"}:
                return normalized
            raise ValueError("COOKIE_SAMESITE must be one of: lax, strict, none")
        return value

    @field_validator("FRONTEND_URL", mode="before")
    @classmethod
    def normalize_frontend_url(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        url = value.strip().rstrip("/")
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("FRONTEND_URL must be an absolute http(s) URL")
        if parsed.path or parsed.params or parsed.query or parsed.fragment:
            raise ValueError("FRONTEND_URL must contain only an origin (no path, query, or fragment)")
        return url

    @field_validator("GOOGLE_REDIRECT_URI", mode="before")
    @classmethod
    def normalize_google_redirect_uri(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        url = value.strip()
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("GOOGLE_REDIRECT_URI must be an absolute http(s) URL")
        if not parsed.path.endswith("/auth/google/callback"):
            raise ValueError("GOOGLE_REDIRECT_URI must end with /auth/google/callback")
        if parsed.params or parsed.query or parsed.fragment:
            raise ValueError("GOOGLE_REDIRECT_URI cannot contain parameters, a query, or a fragment")
        return url

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def normalize_cors_origins(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized: list[str] = []
        for raw_origin in value.split(","):
            origin = raw_origin.strip().rstrip("/")
            if not origin:
                continue
            parsed = urllib.parse.urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"Invalid CORS origin: {raw_origin.strip()}")
            if parsed.path or parsed.params or parsed.query or parsed.fragment:
                raise ValueError(f"CORS origins cannot contain a path, query, or fragment: {raw_origin.strip()}")
            normalized.append(origin)
        if not normalized:
            raise ValueError("CORS_ORIGINS must contain at least one origin")
        return ",".join(normalized)

    @property
    def cors_origins(self) -> list[str]:
        origins = {origin.strip().rstrip("/") for origin in self.CORS_ORIGINS.split(",") if origin.strip()}
        frontend = self.FRONTEND_URL.strip().rstrip("/")
        if frontend:
            origins.add(frontend)
        return sorted(origins)

    @property
    def cors_origin_regex(self) -> str | None:
        regex = self.CORS_ORIGIN_REGEX.strip() if self.CORS_ORIGIN_REGEX else ""
        return regex or None

    @property
    def frontend_hostname(self) -> str | None:
        parsed = urllib.parse.urlparse(self.FRONTEND_URL)
        return parsed.hostname

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
