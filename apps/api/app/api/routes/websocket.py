import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.exceptions import RedisError
from sqlalchemy import select

from app.api.routes.conversations import message_event_data
from app.core.exceptions import AppError, AuthenticationError
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.models.conversation_member import ConversationMember
from app.repositories.user_repository import UserRepository
from app.services.message_service import MessageService
from app.services.presence_service import mark_offline, mark_online
from app.services.typing_service import set_typing
from app.websocket.manager import connection_manager, event_envelope

router = APIRouter(tags=["WebSocket"])


async def member_ids(session, conversation_id: uuid.UUID) -> list[uuid.UUID]:
    result = await session.scalars(
        select(ConversationMember.user_id).where(
            ConversationMember.conversation_id == conversation_id
        )
    )
    return list(result)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = websocket.cookies.get("access_token") or websocket.query_params.get("token")
    if not token:
        # Accept first so browsers receive the application close code instead of
        # an HTTP 403 handshake failure that looks like a transient network error.
        await websocket.accept()
        await websocket.close(code=4401, reason="Missing access token")
        return
    try:
        claims = decode_token(token, expected_type="access")
        user_id = uuid.UUID(claims["sub"])
    except (AuthenticationError, ValueError, TypeError):
        await websocket.accept()
        await websocket.close(code=4401, reason="Invalid access token")
        return

    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_id(user_id)
        if not user or not user.is_active:
            await websocket.accept()
            await websocket.close(code=4401, reason="Account unavailable")
            return
        await connection_manager.connect(user_id=user_id, websocket=websocket)
        try:
            try:
                await mark_online(user_id)
            except RedisError:
                pass
            await websocket.send_json(event_envelope("connection.ready", {"user_id": str(user_id)}))
            while True:
                data: dict = {}
                try:
                    event = await websocket.receive_json()
                    if not isinstance(event, dict):
                        raise TypeError("WebSocket events must be JSON objects.")
                    event_type = event.get("event_type")
                    raw_data = event.get("data") or {}
                    if not isinstance(raw_data, dict):
                        raise TypeError("Event data must be a JSON object.")
                    data = raw_data
                    if event_type == "message.send":
                        conversation_id = uuid.UUID(data["conversation_id"])
                        message = await MessageService(session).send_text_message(
                            current_user=user,
                            conversation_id=conversation_id,
                            client_message_id=uuid.UUID(data["client_message_id"]),
                            content=str(data.get("content", "")),
                        )
                        payload = event_envelope(
                            "message.created",
                            {
                                "message_id": str(message.id),
                                "conversation_id": str(message.conversation_id),
                                "sender_id": str(message.sender_id),
                                "client_message_id": str(message.client_message_id),
                                "type": message.type,
                                "content": message.content,
                                "status": message.status,
                                "created_at": message.created_at.isoformat(),
                            },
                        )
                        await connection_manager.broadcast_to_users(
                            user_ids=await member_ids(session, conversation_id), payload=payload
                        )
                    elif event_type == "typing.set":
                        conversation_id = uuid.UUID(data["conversation_id"])
                        await MessageService(session).require_membership(conversation_id, user_id)
                        is_typing = bool(data.get("is_typing", False))
                        try:
                            await set_typing(
                                conversation_id=conversation_id,
                                user_id=user_id,
                                is_typing=is_typing,
                            )
                        except RedisError:
                            pass
                        await connection_manager.broadcast_to_users(
                            user_ids=await member_ids(session, conversation_id),
                            payload=event_envelope(
                                "typing.changed",
                                {
                                    "conversation_id": str(conversation_id),
                                    "user_id": str(user_id),
                                    "is_typing": is_typing,
                                },
                            ),
                        )
                    elif event_type == "message.reaction.toggle":
                        conversation_id = uuid.UUID(data["conversation_id"])
                        message_id = uuid.UUID(data["message_id"])
                        emoji = str(data.get("emoji", ""))
                        message = await MessageService(session).toggle_reaction(
                            conversation_id=conversation_id,
                            message_id=message_id,
                            user_id=user_id,
                            emoji=emoji,
                        )
                        await connection_manager.broadcast_to_users(
                            user_ids=await member_ids(session, conversation_id),
                            payload=event_envelope("message.reaction_updated", message_event_data(message)),
                        )
                    elif event_type == "ping":
                        await websocket.send_json(event_envelope("pong", {}))
                    else:
                        await websocket.send_json(
                            event_envelope("error", {"code": "UNSUPPORTED_EVENT", "message": "Unsupported event type."})
                        )
                except (KeyError, ValueError, TypeError) as exc:
                    await websocket.send_json(
                        event_envelope(
                            "error",
                            {
                                "code": "INVALID_EVENT",
                                "message": str(exc),
                                "conversation_id": data.get("conversation_id"),
                                "client_message_id": data.get("client_message_id"),
                            },
                        )
                    )
                except AppError as exc:
                    await websocket.send_json(
                        event_envelope(
                            "error",
                            {
                                "code": exc.code,
                                "message": exc.message,
                                "conversation_id": data.get("conversation_id"),
                                "client_message_id": data.get("client_message_id"),
                            },
                        )
                    )
                    
        except WebSocketDisconnect:
            pass
        finally:
            connection_manager.disconnect(user_id=user_id, websocket=websocket)
            
            try:
                remaining_connections = await mark_offline(user_id)
                if remaining_connections == 0:
                    user.last_seen_at = datetime.now(UTC)
                    await session.commit()
            except RedisError:
                pass
