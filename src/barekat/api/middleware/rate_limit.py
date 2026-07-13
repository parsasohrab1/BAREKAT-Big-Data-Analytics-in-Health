"""Redis-backed rate limiting middleware."""

from __future__ import annotations

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from barekat.config.settings import get_settings

# Paths with stricter limits
_LOGIN_PATHS = {"/api/v1/auth/login", "/api/v1/auth/mfa/verify"}
_SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        if path in _SKIP_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        limit = settings.rate_limit_login_per_minute if path in _LOGIN_PATHS else settings.rate_limit_per_minute
        window = 60

        key = f"ratelimit:{client_ip}:{path}"
        allowed = _check_rate(key, limit, window)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        return response


def _check_rate(key: str, limit: int, window: int) -> bool:
    try:
        import redis

        settings = get_settings()
        r = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
        pipe = r.pipeline()
        now = time.time()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window)
        _, _, count, _ = pipe.execute()
        return count <= limit
    except Exception:
        # Fail open if Redis unavailable (dev)
        return True
