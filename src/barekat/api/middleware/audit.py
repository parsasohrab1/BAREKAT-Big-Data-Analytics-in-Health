"""FastAPI middleware for access audit logging."""

from __future__ import annotations

import re
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from barekat.config.settings import get_settings
from barekat.security.audit import log_access
from barekat.security.auth import decode_token

_SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}
_PHI_PATH_PATTERNS = [
    (re.compile(r"/api/v1/patients/([^/]+)"), "patient"),
    (re.compile(r"/api/v1/imaging/studies/([^/]+)"), "imaging"),
    (re.compile(r"/api/v1/ml/.*/notes"), "clinical_notes"),
    (re.compile(r"/api/v1/compliance"), "compliance"),
]


def _extract_patient_id(path: str) -> str | None:
    for pattern, _ in _PHI_PATH_PATTERNS:
        match = pattern.search(path)
        if match:
            candidate = match.group(1)
            if candidate and not candidate.startswith("?"):
                return candidate
    return None


def _extract_user(request: Request) -> tuple[str | None, str | None]:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None, None
    try:
        payload = decode_token(auth.split(" ", 1)[1])
        return payload.get("sub"), payload.get("role")
    except ValueError:
        return None, None


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        path = request.url.path

        if not settings.audit_enabled or path in _SKIP_PATHS:
            return await call_next(request)

        response = await call_next(request)

        if not path.startswith("/api/"):
            return response

        username, role = _extract_user(request)
        patient_id = _extract_patient_id(path)
        resource_type = "api"
        for pattern, rtype in _PHI_PATH_PATTERNS:
            if pattern.search(path):
                resource_type = rtype
                break

        action = f"{request.method.lower()}_{path.strip('/').replace('/', '_')}"
        if response.status_code >= 400:
            action = f"denied_{action}" if response.status_code in (401, 403) else action

        try:
            log_access(
                action=action,
                resource=path,
                username=username,
                role=role,
                patient_id=patient_id,
                resource_type=resource_type,
                http_method=request.method,
                status_code=response.status_code,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        except Exception:
            pass  # never block request on audit failure

        return response
