from typing import Literal

from pydantic import BaseModel, Field


class SupportMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4_000)


class SupportChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4_000)
    history: list[SupportMessage] = Field(default_factory=list, max_length=20)
    available_conversations: list[str] = Field(default_factory=list, max_length=100)


class SupportAction(BaseModel):
    type: Literal["login", "logout", "open_chat", "find_people"]
    label: str = Field(min_length=1, max_length=80)
    target: str | None = Field(default=None, max_length=100)


class SupportAssistantResult(BaseModel):
    reply: str
    actions: list[SupportAction] = Field(default_factory=list, max_length=2)


class SupportChatResponse(SupportAssistantResult):
    model: str
