import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.message import MessageResponse
from app.schemas.user import UserResponse


class DirectConversationRequest(BaseModel):
    target_user_id: uuid.UUID


class ConversationMemberResponse(BaseModel):
    user_id: uuid.UUID
    role: str
    user: UserResponse
    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    id: uuid.UUID
    type: str
    title: str | None
    avatar_url: str | None
    creator_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    members: list[ConversationMemberResponse] = Field(default_factory=list)
    last_message: MessageResponse | None = None
    unread_count: int = 0
    model_config = ConfigDict(from_attributes=True)
