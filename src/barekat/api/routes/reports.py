"""Weekly reports and notification preferences API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from barekat.security.rbac import require_permission, require_role, Role
from barekat.storage.database import engine
from barekat.tenant.context import get_current_tenant

router = APIRouter()


class NotificationPrefIn(BaseModel):
    user_email: str
    phone: str | None = None
    email_enabled: bool = True
    sms_enabled: bool = True
    alert_min_severity: str = Field(default="critical", pattern="^(low|medium|high|critical)$")
    weekly_report: bool = True


@router.get("/weekly/summary")
def weekly_summary(user: dict = Depends(require_permission("read"))):
    from barekat.services.reports import collect_weekly_metrics

    tenant = get_current_tenant()
    tenant_id = (tenant.tenant_id if tenant else None) or user.get("tenant_id", "default")
    return collect_weekly_metrics(tenant_id)


@router.get("/weekly/export/excel")
def weekly_export_excel(user: dict = Depends(require_permission("export"))):
    from barekat.services.reports import collect_weekly_metrics, generate_excel_report

    tenant = get_current_tenant()
    tenant_id = (tenant.tenant_id if tenant else None) or user.get("tenant_id", "default")
    metrics = collect_weekly_metrics(tenant_id)
    content = generate_excel_report(metrics)
    filename = f"weekly_{tenant_id}_{metrics['period_end']}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/weekly/export/pdf")
def weekly_export_pdf(user: dict = Depends(require_permission("export"))):
    from barekat.services.reports import collect_weekly_metrics, generate_pdf_report

    tenant = get_current_tenant()
    tenant_id = (tenant.tenant_id if tenant else None) or user.get("tenant_id", "default")
    metrics = collect_weekly_metrics(tenant_id)
    content = generate_pdf_report(metrics)
    filename = f"weekly_{tenant_id}_{metrics['period_end']}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/weekly/html", response_class=HTMLResponse)
def weekly_export_html(user: dict = Depends(require_permission("read"))):
    from barekat.services.reports import collect_weekly_metrics, generate_weekly_html

    tenant = get_current_tenant()
    tenant_id = (tenant.tenant_id if tenant else None) or user.get("tenant_id", "default")
    metrics = collect_weekly_metrics(tenant_id)
    return generate_weekly_html(metrics)


@router.post("/weekly/trigger")
def trigger_weekly_report(user: dict = Depends(require_role(Role.ADMIN, Role.PLATFORM_ADMIN))):
    from barekat.worker.tasks import run_weekly_reports

    task = run_weekly_reports.delay()
    return {"status": "queued", "task_id": task.id}


@router.get("/weekly/archives")
def list_weekly_archives(
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_permission("read")),
):
    tenant = get_current_tenant()
    tenant_id = (tenant.tenant_id if tenant else None) or user.get("tenant_id", "default")
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT report_id, tenant_id, period_start, period_end, excel_path, pdf_path, created_at
                FROM reports.weekly_archives
                WHERE tenant_id = :tenant_id
                ORDER BY created_at DESC LIMIT :limit
            """),
            {"tenant_id": tenant_id, "limit": limit},
        ).mappings().all()
    return {"archives": [dict(r) for r in rows]}


@router.get("/notifications/preferences")
def list_notification_prefs(user: dict = Depends(require_role(Role.ADMIN, Role.PLATFORM_ADMIN))):
    tenant = get_current_tenant()
    tenant_id = (tenant.tenant_id if tenant else None) or user.get("tenant_id", "default")
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT pref_id, user_email, phone, email_enabled, sms_enabled,
                       alert_min_severity, weekly_report
                FROM tenant.notification_preferences WHERE tenant_id = :tenant_id
            """),
            {"tenant_id": tenant_id},
        ).mappings().all()
    return {"preferences": [dict(r) for r in rows]}


@router.put("/notifications/preferences")
def upsert_notification_pref(
    body: NotificationPrefIn,
    user: dict = Depends(require_role(Role.ADMIN, Role.PLATFORM_ADMIN)),
):
    tenant = get_current_tenant()
    tenant_id = (tenant.tenant_id if tenant else None) or user.get("tenant_id", "default")
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO tenant.notification_preferences
                    (tenant_id, user_email, phone, email_enabled, sms_enabled, alert_min_severity, weekly_report)
                VALUES (:tenant_id, :user_email, :phone, :email_enabled, :sms_enabled, :alert_min_severity, :weekly_report)
                ON CONFLICT (tenant_id, user_email) DO UPDATE SET
                    phone = EXCLUDED.phone,
                    email_enabled = EXCLUDED.email_enabled,
                    sms_enabled = EXCLUDED.sms_enabled,
                    alert_min_severity = EXCLUDED.alert_min_severity,
                    weekly_report = EXCLUDED.weekly_report,
                    updated_at = NOW()
            """),
            {"tenant_id": tenant_id, **body.model_dump()},
        )
    return {"status": "saved", "tenant_id": tenant_id, "email": body.user_email}


@router.get("/notifications/log")
def notification_log(
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(require_role(Role.ADMIN, Role.PLATFORM_ADMIN)),
):
    tenant = get_current_tenant()
    tenant_id = (tenant.tenant_id if tenant else None) or user.get("tenant_id", "default")
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT log_id, channel, recipient_masked, subject, severity, status, created_at
                FROM audit.notification_log
                WHERE tenant_id = :tenant_id OR tenant_id IS NULL
                ORDER BY created_at DESC LIMIT :limit
            """),
            {"tenant_id": tenant_id, "limit": limit},
        ).mappings().all()
    return {"log": [dict(r) for r in rows]}
