import uuid

from app.core.redis import redis_client


async def mark_online(user_id: uuid.UUID) -> int:
    key = f"presence:user:{user_id}:connections"
    count = await redis_client.incr(key)
    await redis_client.expire(key, 90)
    return count


async def mark_offline(user_id: uuid.UUID) -> int:
    key = f"presence:user:{user_id}:connections"
    count = int(await redis_client.get(key) or 0)
    if count <= 1:
        await redis_client.delete(key)
        return 0
    count = await redis_client.decr(key)
    await redis_client.expire(key, 90)
    return count

