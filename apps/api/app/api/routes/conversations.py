import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core.config import get_settings
from app.core.exceptions import ServiceUnavailableError, ValidationError
from app.db.session import get_db_session
from app.models.conversation_member import ConversationMember
from app.models.user import User
from app.repositories.message_repository import MessageRepository
from app.schemas.conversation import ConversationResponse, DirectConversationRequest
from app.schemas.message import MessageResponse, SendMessageRequest, ToggleReactionRequest
from app.services.conversation_service import ConversationService
from app.services.media_storage_service import MediaStorageService
from app.services.message_service import MessageService
from app.websocket.manager import connection_manager, event_envelope

router = APIRouter(prefix="/conversations", tags=["Conversations"])


def message_event_data(message) -> dict:
    reactions = [
        {
            "id": str(r.id),
            "message_id": str(r.message_id),
            "user_id": str(r.user_id),
            "emoji": r.emoji,
            "created_at": r.created_at.isoformat(),
        }
        for r in getattr(message, "reactions", [])
    ]
    return {
        "message_id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "sender_id": str(message.sender_id),
        "client_message_id": str(message.client_message_id),
        "type": message.type,
        "content": message.content,
        "media_filename": message.media_filename,
        "media_content_type": message.media_content_type,
        "media_size": message.media_size,
        "status": message.status,
        "created_at": message.created_at.isoformat(),
        "reactions": reactions,
    }


async def broadcast_message(session: AsyncSession, message) -> None:
    member_result = await session.scalars(
        select(ConversationMember.user_id).where(
            ConversationMember.conversation_id == message.conversation_id
        )
    )
    await connection_manager.broadcast_to_users(
        user_ids=list(member_result),
        payload=event_envelope("message.created", message_event_data(message)),
    )


async def broadcast_reaction_update(session: AsyncSession, message) -> None:
    member_result = await session.scalars(
        select(ConversationMember.user_id).where(
            ConversationMember.conversation_id == message.conversation_id
        )
    )
    await connection_manager.broadcast_to_users(
        user_ids=list(member_result),
        payload=event_envelope("message.reaction_updated", message_event_data(message)),
    )


@router.post("/direct", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_direct(
    payload: DirectConversationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    return await ConversationService(session).create_direct_conversation(
        current_user=current_user, target_user_id=payload.target_user_id
    )


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    return await ConversationService(session).list_for_user(current_user.id)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conversation_id: uuid.UUID,
    before_created_at: str | None = None,
    before_id: uuid.UUID | None = None,
    limit: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    from datetime import datetime

    await MessageService(session).require_membership(conversation_id, current_user.id)
    parsed = datetime.fromisoformat(before_created_at.replace("Z", "+00:00")) if before_created_at else None
    return await MessageRepository(session).list_messages(
        conversation_id=conversation_id,
        before_created_at=parsed,
        before_id=before_id,
        limit=limit,
    )


@router.post(
    "/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED
)
async def send_message(
    conversation_id: uuid.UUID,
    payload: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    message = await MessageService(session).send_text_message(
        current_user=current_user,
        conversation_id=conversation_id,
        client_message_id=payload.client_message_id,
        content=payload.content,
    )
    await broadcast_message(session, message)
    return message


@router.post(
    "/{conversation_id}/media", response_model=MessageResponse, status_code=status.HTTP_201_CREATED
)
async def upload_media(
    conversation_id: uuid.UUID,
    client_message_id: uuid.UUID = Form(),
    file: UploadFile = File(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    message_service = MessageService(session)
    await message_service.require_membership(conversation_id, current_user.id)
    existing = await message_service.find_by_client_id(
        sender_id=current_user.id, client_message_id=client_message_id
    )
    if existing:
        return existing

    limit = get_settings().MAX_UPLOAD_SIZE_MB * 1024 * 1024
    data = await file.read(limit + 1)
    if not data:
        raise ValidationError("The selected file is empty.", code="EMPTY_UPLOAD")
    if len(data) > limit:
        raise ValidationError(
            f"Files must be {get_settings().MAX_UPLOAD_SIZE_MB} MB or smaller.",
            code="UPLOAD_TOO_LARGE",
        )
    filename = (file.filename or "attachment").replace("\\", "/").rsplit("/", 1)[-1][:255]
    content_type = (file.content_type or "application/octet-stream").lower()
    if content_type.startswith("image/") and content_type != "image/svg+xml":
        media_type = "image"
    elif content_type.startswith("video/"):
        media_type = "video"
    elif content_type.startswith("audio/"):
        media_type = "audio"
    else:
        media_type = "file"

    storage = MediaStorageService()
    try:
        object_key = await storage.upload(
            conversation_id=conversation_id,
            filename=filename,
            content_type=content_type,
            data=data,
        )
    except Exception as exc:
        raise ServiceUnavailableError(
            "Media storage is unavailable.", code="MEDIA_STORAGE_UNAVAILABLE"
        ) from exc
    try:
        message = await message_service.send_media_message(
            current_user=current_user,
            conversation_id=conversation_id,
            client_message_id=client_message_id,
            media_type=media_type,
            object_key=object_key,
            filename=filename,
            content_type=content_type,
            size=len(data),
        )
    except Exception:
        await storage.delete(object_key)
        raise
    if message.media_object_key != object_key:
        await storage.delete(object_key)
    await broadcast_message(session, message)
    return message


@router.post("/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_conversation_read(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await MessageService(session).mark_read(
        conversation_id=conversation_id, user_id=current_user.id
    )


@router.post("/{conversation_id}/messages/{message_id}/reactions", response_model=MessageResponse)
async def toggle_message_reaction(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    payload: ToggleReactionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    message = await MessageService(session).toggle_reaction(
        conversation_id=conversation_id,
        message_id=message_id,
        user_id=current_user.id,
        emoji=payload.emoji,
    )
    await broadcast_reaction_update(session, message)
    return message
