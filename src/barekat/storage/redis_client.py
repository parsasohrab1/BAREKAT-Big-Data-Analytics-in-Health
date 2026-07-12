"""Redis cache client for session and query caching."""

import json
from typing import Any

import redis

from barekat.config.settings import get_settings


class CacheClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
        )

    def get(self, key: str) -> Any | None:
        value = self.client.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        serialized = json.dumps(value) if not isinstance(value, str) else value
        self.client.setex(key, ttl_seconds, serialized)

    def delete(self, key: str) -> None:
        self.client.delete(key)

    def ping(self) -> bool:
        return self.client.ping()
