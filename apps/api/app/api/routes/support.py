from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_user
from app.core.config import get_settings
from app.models.user import User
from app.schemas.support import SupportChatRequest, SupportChatResponse
from app.services.ollama_service import OllamaService

router = APIRouter(prefix="/support", tags=["Support Assistant"])


@router.post("/chat", response_model=SupportChatResponse)
async def support_chat(
    payload: SupportChatRequest,
    _current_user: User = Depends(get_current_user),
) -> SupportChatResponse:
    settings = get_settings()
    result = await OllamaService(settings).chat(
        message=payload.message,
        history=payload.history,
        available_conversations=payload.available_conversations,
    )
    return SupportChatResponse(**result.model_dump(), model=settings.OLLAMA_MODEL)
