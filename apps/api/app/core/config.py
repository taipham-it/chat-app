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
