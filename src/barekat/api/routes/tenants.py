"""Multi-tenancy API — tenants, settings, quota, billing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from barekat.security.rbac import Role, get_current_user, require_role
from barekat.tenant.billing import estimate_monthly_bill, get_quota_status, get_usage_summary
from barekat.tenant.context import get_current_tenant
from barekat.tenant.repository import (
    get_tenant,
    list_tenants,
    update_tenant_settings,
)

router = APIRouter()


class TenantSettingsUpdate(BaseModel):
    dashboard_title: str | None = None
    primary_color: str | None = None
    logo_url: str | None = None
    locale: str | None = None
    timezone: str | None = None
    enabled_pages: list[str] | None = None
    fhir_profile: str | None = None
    custom_thresholds: dict[str, float] | None = None


class CreateTenantRequest(BaseModel):
    tenant_id: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-z0-9-]+$")
    slug: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-z0-9-]+$")
    name_fa: str
    name_en: str | None = None
    plan_id: str = "starter"
    contact_email: str | None = None


@router.get("/me")
def current_tenant(user: dict = Depends(get_current_user)):
    ctx = get_current_tenant()
    if not ctx:
        return {"tenant_id": "default", "name_fa": "بیمارستان پیش‌فرض", "settings": {}}
    tenant = get_tenant(ctx.tenant_id)
    return {
        "tenant_id": ctx.tenant_id,
        "slug": ctx.slug,
        "name_fa": ctx.name_fa,
        "plan_id": ctx.plan_id,
        "is_platform_admin": ctx.is_platform_admin,
        "settings": ctx.settings,
        "status": tenant.get("status") if tenant else "active",
    }


@router.get("/me/quota")
def my_quota(user: dict = Depends(get_current_user)):
    ctx = get_current_tenant()
    if not ctx:
        raise HTTPException(status_code=400, detail="No tenant context")
    return get_quota_status(ctx.tenant_id, ctx.plan_id)


@router.get("/me/billing")
def my_billing(user: dict = Depends(get_current_user)):
    ctx = get_current_tenant()
    if not ctx:
        raise HTTPException(status_code=400, detail="No tenant context")
    return estimate_monthly_bill(ctx.tenant_id, ctx.plan_id)


@router.get("/me/usage")
def my_usage(user: dict = Depends(get_current_user)):
    ctx = get_current_tenant()
    if not ctx:
        raise HTTPException(status_code=400, detail="No tenant context")
    return {"usage": get_usage_summary(ctx.tenant_id)}


@router.patch("/me/settings")
def update_my_settings(
    body: TenantSettingsUpdate,
    user: dict = Depends(require_role(Role.ADMIN)),
):
    ctx = get_current_tenant()
    if not ctx:
        raise HTTPException(status_code=400, detail="No tenant context")
    updates = body.model_dump(exclude_none=True)
    return update_tenant_settings(ctx.tenant_id, updates)


@router.get("/")
def list_all_tenants(user: dict = Depends(get_current_user)):
    ctx = get_current_tenant()
    if ctx and ctx.is_platform_admin:
        return {"tenants": list_tenants()}
    if ctx:
        tenant = get_tenant(ctx.tenant_id)
        return {"tenants": [tenant] if tenant else []}
    return {"tenants": list_tenants()}


@router.get("/plans")
def list_plans(user: dict = Depends(get_current_user)):
    from sqlalchemy import text
    from barekat.storage.database import engine

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM tenant.plans WHERE is_active = TRUE")).mappings().all()
    return {"plans": [dict(r) for r in rows]}


@router.get("/{tenant_id}")
def tenant_detail(tenant_id: str, user: dict = Depends(get_current_user)):
    ctx = get_current_tenant()
    if ctx and not ctx.is_platform_admin and ctx.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    tenant = get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    quota = get_quota_status(tenant_id, tenant.get("plan_id", "starter"))
    billing = estimate_monthly_bill(tenant_id, tenant.get("plan_id", "starter"))
    return {"tenant": tenant, "quota": quota, "billing": billing}


@router.post("/")
def create_tenant(body: CreateTenantRequest, user: dict = Depends(require_role(Role.ADMIN))):
    ctx = get_current_tenant()
    if not ctx or not ctx.is_platform_admin:
        raise HTTPException(status_code=403, detail="Platform admin required")

    from sqlalchemy import text
    from barekat.storage.database import engine

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO tenant.tenants (tenant_id, slug, name_fa, name_en, plan_id, contact_email)
            VALUES (:tenant_id, :slug, :name_fa, :name_en, :plan_id, :contact_email)
        """), body.model_dump())
        conn.execute(text("""
            INSERT INTO tenant.tenant_settings (tenant_id, dashboard_title)
            VALUES (:tenant_id, :name_fa)
        """), {"tenant_id": body.tenant_id, "name_fa": body.name_fa})

    return get_tenant(body.tenant_id)
