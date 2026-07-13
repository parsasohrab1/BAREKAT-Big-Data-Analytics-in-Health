"""Request-scoped tenant context for multi-tenancy."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

_current_tenant: ContextVar["TenantContext | None"] = ContextVar("current_tenant", default=None)

DEFAULT_TENANT_ID = "default"


@dataclass
class TenantContext:
    tenant_id: str
    slug: str
    name_fa: str
    plan_id: str = "starter"
    is_platform_admin: bool = False
    settings: dict[str, Any] = field(default_factory=dict)


def set_current_tenant(ctx: TenantContext | None) -> None:
    _current_tenant.set(ctx)


def get_current_tenant() -> TenantContext | None:
    return _current_tenant.get()


def get_tenant_id() -> str:
    ctx = get_current_tenant()
    return ctx.tenant_id if ctx else DEFAULT_TENANT_ID


def require_tenant_id() -> str:
    return get_tenant_id()
