"""Tenant resolution middleware — sets request-scoped tenant context."""

from __future__ import annotations

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from barekat.security.auth import decode_token
from barekat.tenant.billing import METRIC_API_CALLS, record_usage
from barekat.tenant.context import set_current_tenant
from barekat.tenant.repository import resolve_user_tenant


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ctx = None
        requested_tenant = request.headers.get("X-Tenant-ID")

        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            try:
                payload = decode_token(auth.split(" ", 1)[1])
                username = payload.get("sub", "")
                # JWT may carry tenant_id directly (post-login)
                jwt_tenant = payload.get("tenant_id")
                req_tid = requested_tenant or jwt_tenant
                ctx = resolve_user_tenant(username, req_tid)
            except ValueError:
                pass

        if ctx is None and requested_tenant:
            from barekat.tenant.repository import get_tenant, _build_context
            tenant = get_tenant(requested_tenant)
            if tenant:
                ctx = _build_context(tenant)

        set_current_tenant(ctx)
        response = await call_next(request)

        if ctx and request.url.path.startswith("/api/"):
            try:
                record_usage(ctx.tenant_id, METRIC_API_CALLS, 1, {
                    "path": request.url.path,
                    "method": request.method,
                })
            except Exception:
                pass

        if ctx:
            response.headers["X-Tenant-ID"] = ctx.tenant_id
            response.headers["X-Tenant-Slug"] = ctx.slug

        set_current_tenant(None)
        return response
