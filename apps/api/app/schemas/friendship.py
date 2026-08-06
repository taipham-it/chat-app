import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.user import UserResponse


class FriendshipResponse(BaseModel):
    id: uuid.UUID
    status: str
    user: UserResponse
    requested_by_me: bool
    created_at: datetime


class UserSearchResponse(UserResponse):
    friendship_status: str = "none"
    friendship_id: uuid.UUID | None = None

