import uuid

from app.core.redis import redis_client


async def set_typing(*, conversation_id: uuid.UUID, user_id: uuid.UUID, is_typing: bool) -> None:
    key = f"typing:conversation:{conversation_id}:{user_id}"
    if is_typing:
        await redis_client.set(key, "1", ex=5)
    else:
        await redis_client.delete(key)

