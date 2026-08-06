import asyncio
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import WebSocket


def event_envelope(event_type: str, data: dict) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "timestamp": datetime.now(UTC).isoformat(),
        "data": data,
    }


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)

    async def connect(self, *, user_id: uuid.UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[user_id].add(websocket)

    def disconnect(self, *, user_id: uuid.UUID, websocket: WebSocket) -> None:
        connections = self._connections.get(user_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(user_id, None)

    async def send_to_user(self, *, user_id: uuid.UUID, payload: dict) -> None:
        sockets = list(self._connections.get(user_id, set()))
        if not sockets:
            return
        results = await asyncio.gather(
            *(socket.send_json(payload) for socket in sockets), return_exceptions=True
        )
        for socket, result in zip(sockets, results, strict=True):
            if isinstance(result, Exception):
                self.disconnect(user_id=user_id, websocket=socket)

    async def broadcast_to_users(self, *, user_ids: list[uuid.UUID], payload: dict) -> None:
        await asyncio.gather(
            *(self.send_to_user(user_id=user_id, payload=payload) for user_id in set(user_ids))
        )


connection_manager = ConnectionManager()
