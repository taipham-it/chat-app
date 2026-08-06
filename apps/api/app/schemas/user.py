import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserUpdateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    avatar_url: str | None = Field(default=None, max_length=2_000_000)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    username: str
    avatar_url: str | None = None
    is_active: bool
    created_at: datetime
    last_seen_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
