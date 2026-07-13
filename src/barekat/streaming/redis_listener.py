"""Background Redis subscriber that forwards alerts to WebSocket clients."""

from __future__ import annotations

import asyncio
import json
import threading

import redis

from barekat.api.websocket_manager import alert_manager
from barekat.config.settings import get_settings


class RedisAlertSubscriber:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        settings = get_settings()
        client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
        pubsub = client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(settings.redis_alerts_channel)

        while not self._stop.is_set():
            message = pubsub.get_message(timeout=1.0)
            if not message or message.get("type") != "message":
                continue
            try:
                alert = json.loads(message["data"])
            except (json.JSONDecodeError, KeyError):
                continue
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(alert_manager.broadcast(alert), self._loop)
            if alert.get("severity") in ("critical", "high"):
                try:
                    from barekat.worker.tasks import send_alert_notification
                    send_alert_notification.delay(alert)
                except Exception:
                    pass


redis_subscriber = RedisAlertSubscriber()
