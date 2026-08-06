from redis.asyncio import Redis

from app.core.config import get_settings

redis_client = Redis.from_url(get_settings().REDIS_URL, encoding="utf-8", decode_responses=True)

