import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SendMessageRequest(BaseModel):
    client_message_id: uuid.UUID
    content: str = Field(min_length=1, max_length=10_000)


class ToggleReactionRequest(BaseModel):
    emoji: str = Field(min_length=1, max_length=32)


class MessageReactionResponse(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    user_id: uuid.UUID
    emoji: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    client_message_id: uuid.UUID
    type: str
    content: str | None
    media_filename: str | None
    media_content_type: str | None
    media_size: int | None
    status: str
    created_at: datetime
    edited_at: datetime | None
    deleted_at: datetime | None
    reactions: list[MessageReactionResponse] = []
    model_config = ConfigDict(from_attributes=True)
