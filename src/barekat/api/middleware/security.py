"""Security headers and basic WAF pattern blocking."""

from __future__ import annotations

import re
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from barekat.config.settings import get_settings

# Basic WAF patterns (SQLi, path traversal, XSS probes)
_WAF_PATTERNS = [
    re.compile(r"(?i)(union\s+select|drop\s+table|;\s*--|or\s+1\s*=\s*1)"),
    re.compile(r"(?i)(<script|javascript:|onerror\s*=)"),
    re.compile(r"(\.\./|\.\.\\|%2e%2e)"),
    re.compile(r"(?i)(/etc/passwd|/proc/self)"),
]


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()

        if settings.waf_enabled:
            blocked = _waf_check(request)
            if blocked:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Request blocked by WAF policy"},
                )

        response = await call_next(request)

        if settings.tls_enabled or settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        return response


def _waf_check(request: Request) -> bool:
    targets = [
        str(request.url),
        request.url.path,
    ]
    for key, value in request.query_params.items():
        targets.append(f"{key}={value}")
    body = getattr(request.state, "waf_body", None)
    if body:
        targets.append(body)

    for target in targets:
        for pattern in _WAF_PATTERNS:
            if pattern.search(target):
                return True
    return False
