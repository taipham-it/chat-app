import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends
from minio.error import S3Error
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.api.dependencies.auth import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.session import get_db_session
from app.models.message import Message
from app.models.user import User
from app.services.media_storage_service import MediaStorageService
from app.services.message_service import MessageService

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.get("/{message_id}/media")
async def get_message_media(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    message = await session.get(Message, message_id)
    if not message or not message.media_object_key:
        raise NotFoundError("Media not found.", code="MEDIA_NOT_FOUND")
    await MessageService(session).require_membership(message.conversation_id, current_user.id)
    try:
        response = await MediaStorageService().get(message.media_object_key)
    except S3Error as exc:
        if exc.code in {"NoSuchKey", "NoSuchObject"}:
            raise NotFoundError("Media not found.", code="MEDIA_NOT_FOUND") from exc
        raise ServiceUnavailableError("Media storage is unavailable.", code="MEDIA_STORAGE_UNAVAILABLE") from exc

    def stream():
        try:
            yield from response.stream(64 * 1024)
        finally:
            response.close()
            response.release_conn()

    filename = message.media_filename or "attachment"
    disposition = "inline" if message.type in {"image", "video", "audio"} else "attachment"
    headers = {
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(filename)}",
        "Cache-Control": "private, max-age=3600",
        "X-Content-Type-Options": "nosniff",
    }
    if message.media_size is not None:
        headers["Content-Length"] = str(message.media_size)
    return StreamingResponse(
        stream(), media_type=message.media_content_type or "application/octet-stream", headers=headers
    )
