"""Redis pub/sub bridge for real-time alert broadcasting."""

from __future__ import annotations

import json
from typing import Any

import redis

from barekat.config.settings import get_settings


def get_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)


def publish_live_alert(alert: dict[str, Any]) -> None:
    settings = get_settings()
    client = get_redis_client()
    payload = json.dumps(alert, default=str)
    client.publish(settings.redis_alerts_channel, payload)
    client.lpush(settings.redis_alerts_recent_key, payload)
    client.ltrim(settings.redis_alerts_recent_key, 0, settings.redis_alerts_recent_max - 1)


def get_recent_live_alerts(limit: int = 50) -> list[dict[str, Any]]:
    settings = get_settings()
    client = get_redis_client()
    raw = client.lrange(settings.redis_alerts_recent_key, 0, limit - 1)
    alerts = []
    for item in raw:
        try:
            alerts.append(json.loads(item))
        except json.JSONDecodeError:
            continue
    return alerts
