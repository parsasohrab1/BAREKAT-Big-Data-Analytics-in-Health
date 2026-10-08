"""Weekly PDF/Excel executive reports for hospital managers."""

from __future__ import annotations

import io
import json
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import text

from barekat.config.settings import get_settings
from barekat.services.notifications import get_notification_recipients, send_email
from barekat.storage.database import engine

REPORTS_DIR = Path("./data/reports")


def _week_bounds(reference: date | None = None) -> tuple[date, date]:
    ref = reference or date.today()
    start = ref - timedelta(days=ref.weekday() + 7)
    end = start + timedelta(days=6)
    return start, end


def collect_weekly_metrics(tenant_id: str, period_start: date | None = None, period_end: date | None = None) -> dict[str, Any]:
    if period_start is None or period_end is None:
        period_start, period_end = _week_bounds()

    tenant_filter = "AND tenant_id = :tenant_id" if tenant_id else ""
    params: dict[str, Any] = {"start": period_start, "end": period_end, "tenant_id": tenant_id}

    with engine.connect() as conn:
        admissions = conn.execute(text(f"""
            SELECT COUNT(*) AS total,
                   ROUND(AVG(length_of_stay)::numeric, 1) AS avg_los,
                   ROUND(100.0 * AVG(CASE WHEN readmission_flag THEN 1 ELSE 0 END)::numeric, 2) AS readmit_pct
            FROM raw.admissions
            WHERE admission_date::date BETWEEN :start AND :end {tenant_filter}
        """), params).mappings().first() or {}

        alerts = conn.execute(text(f"""
            SELECT severity, COUNT(*) AS cnt
            FROM analytics.predictive_alerts
            WHERE created_at::date BETWEEN :start AND :end {tenant_filter}
            GROUP BY severity
        """), params).mappings().all()

        dept = conn.execute(text(f"""
            SELECT department, COUNT(*) AS cnt
            FROM raw.admissions
            WHERE admission_date::date BETWEEN :start AND :end {tenant_filter}
            GROUP BY department ORDER BY cnt DESC LIMIT 10
        """), params).mappings().all()

        patients = conn.execute(text(f"""
            SELECT COUNT(DISTINCT patient_id) AS cnt FROM raw.admissions
            WHERE admission_date::date BETWEEN :start AND :end {tenant_filter}
        """), params).scalar() or 0

        tenant_name = conn.execute(
            text("SELECT name_fa FROM tenant.tenants WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        ).scalar() or tenant_id

    alert_counts = {r["severity"]: r["cnt"] for r in alerts}
    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "period_start": str(period_start),
        "period_end": str(period_end),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "admissions_total": int(admissions.get("total") or 0),
        "avg_length_of_stay": float(admissions.get("avg_los") or 0),
        "readmission_rate_pct": float(admissions.get("readmit_pct") or 0),
        "unique_patients": int(patients),
        "alerts_by_severity": alert_counts,
        "alerts_critical": alert_counts.get("critical", 0),
        "alerts_high": alert_counts.get("high", 0),
        "top_departments": [dict(d) for d in dept],
    }


def generate_excel_report(metrics: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    summary = pd.DataFrame([{
        "Center": metrics.get("tenant_name"),
        "From date": metrics.get("period_start"),
        "To date": metrics.get("period_end"),
        "Number of admissions": metrics.get("admissions_total"),
        "Average LOS": metrics.get("avg_length_of_stay"),
        "Readmission rate %": metrics.get("readmission_rate_pct"),
        "Unique patients": metrics.get("unique_patients"),
        "Critical alerts": metrics.get("alerts_critical"),
        "High alerts": metrics.get("alerts_high"),
    }])

    alert_rows = [
        {"Severity": k, "Count": v}
        for k, v in (metrics.get("alerts_by_severity") or {}).items()
    ]
    dept_rows = metrics.get("top_departments") or []

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        if alert_rows:
            pd.DataFrame(alert_rows).to_excel(writer, sheet_name="Alerts", index=False)
        if dept_rows:
            pd.DataFrame(dept_rows).rename(columns={"department": "Department", "cnt": "Count"}).to_excel(
                writer, sheet_name="Departments", index=False,
            )

    return buffer.getvalue()


def generate_pdf_report(metrics: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm)
    styles = getSampleStyleSheet()
    story = []

    title = f"BAREKAT Weekly Report — {metrics.get('tenant_name', metrics.get('tenant_id'))}"
    story.append(Paragraph(title, styles["Title"]))
    story.append(Paragraph(
        f"Period: {metrics.get('period_start')} to {metrics.get('period_end')}",
        styles["Normal"],
    ))
    story.append(Spacer(1, 0.5 * cm))

    rows = [
        ["Metric", "Value"],
        ["Admissions", str(metrics.get("admissions_total", 0))],
        ["Unique patients", str(metrics.get("unique_patients", 0))],
        ["Avg LOS (days)", str(metrics.get("avg_length_of_stay", 0))],
        ["Readmission rate %", str(metrics.get("readmission_rate_pct", 0))],
        ["Critical alerts", str(metrics.get("alerts_critical", 0))],
        ["High alerts", str(metrics.get("alerts_high", 0))],
    ]
    table = Table(rows, colWidths=[8 * cm, 6 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0891B2")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.5 * cm))

    dept = metrics.get("top_departments") or []
    if dept:
        dept_rows = [["Department", "Admissions"]] + [[d["department"], str(d["cnt"])] for d in dept]
        dt = Table(dept_rows, colWidths=[8 * cm, 6 * cm])
        dt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
        story.append(Paragraph("Top Departments", styles["Heading2"]))
        story.append(dt)

    doc.build(story)
    return buffer.getvalue()


def generate_weekly_html(metrics: dict[str, Any]) -> str:
    dept_rows = "".join(
        f"<tr><td>{escape(str(d.get('department', '')))}</td><td>{d.get('cnt', 0)}</td></tr>"
        for d in (metrics.get("top_departments") or [])
    )
    alert_rows = "".join(
        f"<tr><td>{escape(k)}</td><td>{v}</td></tr>"
        for k, v in (metrics.get("alerts_by_severity") or {}).items()
    )
    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8"/>
  <title>Weekly report — {escape(str(metrics.get('tenant_name', '')))}</title>
  <style>
  body {{ font-family: Tahoma, sans-serif; max-width: 800px; margin: 2rem auto; color: #1e293b; }}
  h1 {{ color: #0891B2; border-bottom: 2px solid #0891B2; padding-bottom: 0.5rem; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
  th, td {{ border: 1px solid #e2e8f0; padding: 0.5rem; text-align: right; }}
  th {{ background: #f1f5f9; }}
  .kpi {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }}
  .kpi div {{ background: #f0fdfa; border-radius: 8px; padding: 1rem; text-align: center; }}
  .kpi strong {{ font-size: 1.5rem; color: #0f766e; display: block; }}
  </style>
</head>
<body>
  <h1>Weekly management report — {escape(str(metrics.get('tenant_name', '')))}</h1>
  <p>Period: {metrics.get('period_start')} to {metrics.get('period_end')}</p>
  <div class="kpi">
    <div><strong>{metrics.get('admissions_total', 0)}</strong>Admissions</div>
    <div><strong>{metrics.get('readmission_rate_pct', 0)}%</strong>Readmission</div>
    <div><strong>{metrics.get('alerts_critical', 0)}</strong>Critical alerts</div>
  </div>
  <h2>Alerts by severity</h2>
  <table><tr><th>Severity</th><th>Count</th></tr>{alert_rows or '<tr><td colspan=2>—</td></tr>'}</table>
  <h2>Busiest departments</h2>
  <table><tr><th>Department</th><th>Count</th></tr>{dept_rows or '<tr><td colspan=2>—</td></tr>'}</table>
</body>
</html>"""


def archive_report(tenant_id: str, metrics: dict[str, Any], excel_bytes: bytes, pdf_bytes: bytes) -> str:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    period = metrics.get("period_end", date.today().isoformat())
    base = f"{tenant_id}_{period}"
    excel_path = REPORTS_DIR / f"{base}.xlsx"
    pdf_path = REPORTS_DIR / f"{base}.pdf"
    excel_path.write_bytes(excel_bytes)
    pdf_path.write_bytes(pdf_bytes)

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO reports.weekly_archives
                    (tenant_id, period_start, period_end, excel_path, pdf_path, metrics)
                VALUES (:tenant_id, :period_start, :period_end, :excel_path, :pdf_path, CAST(:metrics AS jsonb))
            """),
            {
                "tenant_id": tenant_id,
                "period_start": metrics["period_start"],
                "period_end": metrics["period_end"],
                "excel_path": str(excel_path),
                "pdf_path": str(pdf_path),
                "metrics": json.dumps(metrics),
            },
        )
    return str(excel_path)


def send_weekly_report_to_managers(tenant_id: str) -> dict[str, Any]:
    metrics = collect_weekly_metrics(tenant_id)
    excel_bytes = generate_excel_report(metrics)
    pdf_bytes = generate_pdf_report(metrics)
    archive_path = archive_report(tenant_id, metrics, excel_bytes, pdf_bytes)

    html = generate_weekly_html(metrics)
    subject = f"BAREKAT Weekly Report — {metrics.get('tenant_name', tenant_id)}"
    attachments = [
        (f"weekly_{tenant_id}.xlsx", excel_bytes),
        (f"weekly_{tenant_id}.pdf", pdf_bytes),
    ]

    sent = 0
    for rec in get_notification_recipients(tenant_id, weekly_only=True):
        if rec.get("email_enabled") and rec.get("user_email"):
            if send_email(rec["user_email"], subject, html, attachments=attachments):
                sent += 1

    return {"tenant_id": tenant_id, "emails_sent": sent, "archive": archive_path, "metrics": metrics}


def list_tenant_ids() -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT tenant_id FROM tenant.tenants WHERE status = 'active'")).scalars().all()
    if rows:
        return list(rows)
    return [get_settings().default_tenant_id]
