from redis import Redis

from app.core.config import get_settings


class RedisCacheClient:
    """Thin Redis client wrapper used to keep cache access behind a stable interface."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = Redis.from_url(settings.redis_url, decode_responses=True)

    def ping(self) -> bool:
        return bool(self._client.ping())

