"""Tenant data access, settings, and listing."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from barekat.storage.database import engine
from barekat.tenant.context import DEFAULT_TENANT_ID, TenantContext


def get_tenant(tenant_id: str) -> dict[str, Any] | None:
    query = text("""
        SELECT t.tenant_id, t.slug, t.name_fa, t.name_en, t.plan_id, t.status,
               t.contact_email, t.created_at,
               s.logo_url, s.primary_color, s.locale, s.timezone,
               s.enabled_pages, s.custom_thresholds, s.fhir_profile, s.dashboard_title
        FROM tenant.tenants t
        LEFT JOIN tenant.tenant_settings s ON s.tenant_id = t.tenant_id
        WHERE t.tenant_id = :tenant_id
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"tenant_id": tenant_id}).mappings().first()
    return dict(row) if row else None


def get_tenant_by_slug(slug: str) -> dict[str, Any] | None:
    query = text("SELECT tenant_id FROM tenant.tenants WHERE slug = :slug")
    with engine.connect() as conn:
        tid = conn.execute(query, {"slug": slug}).scalar()
    return get_tenant(tid) if tid else None


def list_tenants(*, status: str | None = "active") -> list[dict[str, Any]]:
    conditions = ["1=1"]
    params: dict[str, Any] = {}
    if status:
        conditions.append("status = :status")
        params["status"] = status
    query = text(f"""
        SELECT tenant_id, slug, name_fa, name_en, plan_id, status, contact_email, created_at
        FROM tenant.tenants
        WHERE {' AND '.join(conditions)}
        ORDER BY name_fa
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, params).mappings().all()
    return [dict(r) for r in rows]


def resolve_user_tenant(username: str, requested_tenant_id: str | None = None) -> TenantContext | None:
    """Resolve tenant for user. Platform admin may switch via requested_tenant_id."""
    memberships = _user_memberships(username)
    if not memberships:
        # Dev fallback — default tenant
        return _build_context(get_tenant(DEFAULT_TENANT_ID) or _default_tenant_dict())

    is_platform = any(m.get("role") == "platform_admin" for m in memberships)

    if requested_tenant_id and is_platform:
        tenant = get_tenant(requested_tenant_id)
        if tenant:
            ctx = _build_context(tenant)
            ctx.is_platform_admin = True
            return ctx

    primary = next((m for m in memberships if m.get("is_primary")), memberships[0])
    tenant = get_tenant(primary["tenant_id"])
    if not tenant:
        return None
    ctx = _build_context(tenant)
    ctx.is_platform_admin = is_platform
    return ctx


def _user_memberships(username: str) -> list[dict[str, Any]]:
    query = text("""
        SELECT tenant_id, role, is_primary FROM tenant.tenant_users
        WHERE username = :username
    """)
    try:
        with engine.connect() as conn:
            rows = conn.execute(query, {"username": username}).mappings().all()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _build_context(tenant: dict[str, Any]) -> TenantContext:
    enabled = tenant.get("enabled_pages")
    if isinstance(enabled, str):
        enabled = json.loads(enabled)
    settings = {
        "logo_url": tenant.get("logo_url"),
        "primary_color": tenant.get("primary_color", "#0891B2"),
        "locale": tenant.get("locale", "fa"),
        "timezone": tenant.get("timezone", "Asia/Tehran"),
        "enabled_pages": enabled or [],
        "custom_thresholds": tenant.get("custom_thresholds") or {},
        "fhir_profile": tenant.get("fhir_profile", "iran_moh"),
        "dashboard_title": tenant.get("dashboard_title"),
    }
    return TenantContext(
        tenant_id=tenant["tenant_id"],
        slug=tenant["slug"],
        name_fa=tenant["name_fa"],
        plan_id=tenant.get("plan_id", "starter"),
        settings=settings,
    )


def _default_tenant_dict() -> dict[str, Any]:
    return {
        "tenant_id": DEFAULT_TENANT_ID,
        "slug": "default",
        "name_fa": "بیمارستان پیش‌فرض",
        "plan_id": "professional",
        "primary_color": "#0891B2",
        "enabled_pages": [],
        "dashboard_title": "BAREKAT",
    }


def get_plan(plan_id: str) -> dict[str, Any] | None:
    query = text("SELECT * FROM tenant.plans WHERE plan_id = :plan_id")
    with engine.connect() as conn:
        row = conn.execute(query, {"plan_id": plan_id}).mappings().first()
    return dict(row) if row else None


def update_tenant_settings(tenant_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    allowed = {"logo_url", "primary_color", "locale", "timezone", "enabled_pages",
               "custom_thresholds", "fhir_profile", "dashboard_title"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return get_tenant(tenant_id) or {}

    sets = ", ".join(f"{k} = :{k}" for k in fields)
    if "enabled_pages" in fields and isinstance(fields["enabled_pages"], list):
        fields["enabled_pages"] = json.dumps(fields["enabled_pages"])
    if "custom_thresholds" in fields and isinstance(fields["custom_thresholds"], dict):
        fields["custom_thresholds"] = json.dumps(fields["custom_thresholds"])

    query = text(f"""
        UPDATE tenant.tenant_settings SET {sets}, updated_at = NOW()
        WHERE tenant_id = :tenant_id
    """)
    with engine.begin() as conn:
        conn.execute(query, {"tenant_id": tenant_id, **fields})
    return get_tenant(tenant_id) or {}
