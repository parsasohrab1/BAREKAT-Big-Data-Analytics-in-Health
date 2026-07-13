"""Email/SMS notifications for critical alerts and weekly reports."""

from __future__ import annotations

import re
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx
import structlog
from sqlalchemy import text

from barekat.config.settings import get_settings
from barekat.storage.database import engine

logger = structlog.get_logger(__name__)

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _mask_recipient(value: str) -> str:
    if "@" in value:
        local, domain = value.split("@", 1)
        return f"{local[:2]}***@{domain}"
    if len(value) > 4:
        return f"{value[:4]}***"
    return "***"


def _meets_threshold(severity: str, min_severity: str) -> bool:
    return SEVERITY_RANK.get(severity, 0) >= SEVERITY_RANK.get(min_severity, 4)


def log_notification(
    *,
    tenant_id: str | None,
    channel: str,
    recipient: str,
    subject: str,
    severity: str | None = None,
    alert_id: str | None = None,
    status: str = "sent",
    error_message: str | None = None,
) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO audit.notification_log
                        (tenant_id, channel, recipient_masked, subject, alert_id, severity, status, error_message)
                    VALUES (:tenant_id, :channel, :recipient_masked, :subject, :alert_id, :severity, :status, :error_message)
                """),
                {
                    "tenant_id": tenant_id,
                    "channel": channel,
                    "recipient_masked": _mask_recipient(recipient),
                    "subject": subject[:500] if subject else None,
                    "alert_id": alert_id,
                    "severity": severity,
                    "status": status,
                    "error_message": error_message,
                },
            )
    except Exception as exc:
        logger.warning("notification_log_failed", error=str(exc))


def get_notification_recipients(tenant_id: str, *, weekly_only: bool = False) -> list[dict[str, Any]]:
    query = text("""
        SELECT user_email, phone, email_enabled, sms_enabled, alert_min_severity, weekly_report
        FROM tenant.notification_preferences
        WHERE tenant_id = :tenant_id
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"tenant_id": tenant_id}).mappings().all()
    recipients = [dict(r) for r in rows]
    if weekly_only:
        return [r for r in recipients if r.get("weekly_report")]
    return recipients


def send_email(
    to: str,
    subject: str,
    body_html: str,
    *,
    attachments: list[tuple[str, bytes]] | None = None,
) -> bool:
    settings = get_settings()
    if not settings.notifications_enabled or not settings.smtp_host:
        logger.info("email_skipped", to=_mask_recipient(to), reason="notifications_disabled")
        log_notification(
            tenant_id=None, channel="email", recipient=to, subject=subject, status="skipped",
            error_message="notifications_disabled",
        )
        return False

    msg = MIMEMultipart()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    for filename, content in attachments or []:
        part = MIMEApplication(content, Name=filename)
        part["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(part)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from, [to], msg.as_string())
        log_notification(tenant_id=None, channel="email", recipient=to, subject=subject, status="sent")
        return True
    except Exception as exc:
        logger.error("email_failed", to=_mask_recipient(to), error=str(exc))
        log_notification(
            tenant_id=None, channel="email", recipient=to, subject=subject,
            status="failed", error_message=str(exc),
        )
        return False


def send_sms(to: str, message: str) -> bool:
    settings = get_settings()
    phone = re.sub(r"\D", "", to)
    if not settings.notifications_enabled:
        logger.info("sms_skipped", to=_mask_recipient(phone), reason="notifications_disabled")
        log_notification(
            tenant_id=None, channel="sms", recipient=phone, subject=message[:80],
            status="skipped", error_message="notifications_disabled",
        )
        return False

    if settings.sms_provider == "twilio" and settings.twilio_account_sid:
        return _send_twilio_sms(phone, message)
    if settings.sms_provider == "kavenegar" and settings.kavenegar_api_key:
        return _send_kavenegar_sms(phone, message)

    logger.info("sms_skipped", to=_mask_recipient(phone), reason="no_sms_provider")
    log_notification(
        tenant_id=None, channel="sms", recipient=phone, subject=message[:80],
        status="skipped", error_message="no_sms_provider",
    )
    return False


def _send_twilio_sms(phone: str, message: str) -> bool:
    settings = get_settings()
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                url,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                data={"From": settings.twilio_from_number, "To": phone, "Body": message},
            )
            resp.raise_for_status()
        log_notification(tenant_id=None, channel="sms", recipient=phone, subject=message[:80], status="sent")
        return True
    except Exception as exc:
        log_notification(
            tenant_id=None, channel="sms", recipient=phone, subject=message[:80],
            status="failed", error_message=str(exc),
        )
        return False


def _send_kavenegar_sms(phone: str, message: str) -> bool:
    settings = get_settings()
    url = f"https://api.kavenegar.com/v1/{settings.kavenegar_api_key}/sms/send.json"
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, data={"receptor": phone, "message": message})
            resp.raise_for_status()
        log_notification(tenant_id=None, channel="sms", recipient=phone, subject=message[:80], status="sent")
        return True
    except Exception as exc:
        log_notification(
            tenant_id=None, channel="sms", recipient=phone, subject=message[:80],
            status="failed", error_message=str(exc),
        )
        return False


def dispatch_critical_alert(alert: dict[str, Any], tenant_id: str = "default") -> dict[str, int]:
    """Send email/SMS for critical (or configured min severity) alerts."""
    settings = get_settings()
    severity = alert.get("severity", "medium")
    if not _meets_threshold(severity, settings.alert_notify_min_severity):
        return {"email": 0, "sms": 0}

    recipients = get_notification_recipients(tenant_id)
    if not recipients:
        tenant_email = _tenant_contact_email(tenant_id)
        if tenant_email:
            recipients = [{"user_email": tenant_email, "phone": None, "email_enabled": True, "sms_enabled": False}]

    sent = {"email": 0, "sms": 0}
    subject = f"[BAREKAT] هشدار {severity.upper()} — {alert.get('alert_type', 'alert')}"
    body = _alert_email_html(alert, tenant_id)
    sms_text = (
        f"BAREKAT {severity}: {alert.get('alert_type')} "
        f"بیمار {alert.get('patient_id')} — {alert.get('message', '')[:120]}"
    )

    for rec in recipients:
        min_sev = rec.get("alert_min_severity", "critical")
        if not _meets_threshold(severity, min_sev):
            continue
        if rec.get("email_enabled") and rec.get("user_email"):
            if send_email(rec["user_email"], subject, body):
                sent["email"] += 1
        if rec.get("sms_enabled") and rec.get("phone"):
            if send_sms(rec["phone"], sms_text):
                sent["sms"] += 1

    return sent


def _tenant_contact_email(tenant_id: str) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT contact_email FROM tenant.tenants WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        ).mappings().first()
    return row["contact_email"] if row else None


def _alert_email_html(alert: dict[str, Any], tenant_id: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head><meta charset="utf-8"/></head>
<body style="font-family:Tahoma,sans-serif;max-width:600px;margin:auto">
  <h2 style="color:#dc2626">هشدار بحرانی BAREKAT</h2>
  <p><strong>مرکز:</strong> {tenant_id}</p>
  <p><strong>نوع:</strong> {alert.get('alert_type', '—')}</p>
  <p><strong>شدت:</strong> {alert.get('severity', '—')}</p>
  <p><strong>بیمار:</strong> {alert.get('patient_id', '—')}</p>
  <p><strong>بستری:</strong> {alert.get('admission_id', '—')}</p>
  <p><strong>امتیاز ریسک:</strong> {alert.get('risk_score', '—')}</p>
  <p>{alert.get('message', '')}</p>
  <hr/>
  <p style="font-size:12px;color:#64748b">این پیام خودکار است — لطفاً در داشبورد BAREKAT بررسی کنید.</p>
</body>
</html>"""
