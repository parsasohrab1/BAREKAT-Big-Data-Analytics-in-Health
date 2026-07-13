"""Predictive alerts persistence and retrieval."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from barekat.storage.database import engine


def persist_alerts(alerts_df: pd.DataFrame, alert_type: str = "readmission_risk", replace: bool = True) -> int:
    """Save ML-generated alerts to analytics.predictive_alerts."""
    if alerts_df.empty:
        return 0

    records = alerts_df.copy()
    records.columns = [c.lower() for c in records.columns]

    db_df = records[[
        c for c in [
            "patient_id", "admission_id", "alert_type",
            "severity", "message", "risk_score",
        ]
        if c in records.columns
    ]].copy()

    if "alert_type" not in db_df.columns:
        db_df["alert_type"] = alert_type

    with engine.begin() as conn:
        if replace:
            conn.execute(
                text("DELETE FROM analytics.predictive_alerts WHERE alert_type = :alert_type"),
                {"alert_type": alert_type},
            )
        db_df.to_sql("predictive_alerts", conn, schema="analytics", if_exists="append", index=False)

    for _, row in db_df.iterrows():
        if row.get("severity") in ("critical", "high"):
            _queue_critical_notification(row.to_dict())

    return len(db_df)


def persist_streaming_alert(alert: dict) -> int:
    """Insert a single real-time streaming alert without deleting existing rows."""
    db_df = pd.DataFrame([{
        "patient_id": alert.get("patient_id"),
        "admission_id": alert.get("admission_id", ""),
        "alert_type": alert.get("alert_type", "stream"),
        "severity": alert.get("severity", "medium"),
        "message": alert.get("message", ""),
        "risk_score": alert.get("risk_score", 0),
    }])
    with engine.begin() as conn:
        db_df.to_sql("predictive_alerts", conn, schema="analytics", if_exists="append", index=False)

    _queue_critical_notification(alert)
    return 1


def _queue_critical_notification(alert: dict, tenant_id: str = "default") -> None:
    if alert.get("severity") not in ("critical", "high"):
        return
    try:
        from barekat.worker.tasks import send_alert_notification
        send_alert_notification.delay(alert, tenant_id=tenant_id)
    except Exception:
        try:
            from barekat.services.notifications import dispatch_critical_alert
            dispatch_critical_alert(alert, tenant_id=tenant_id)
        except Exception:
            pass


def load_active_alerts(limit: int = 200) -> pd.DataFrame:
    """Load unacknowledged alerts joined with admission department."""
    query = text("""
        SELECT
            a.alert_id,
            a.patient_id,
            a.admission_id,
            a.alert_type,
            a.severity,
            a.message,
            a.risk_score,
            a.is_acknowledged,
            a.created_at,
            adm.department,
            adm.readmission_flag
        FROM analytics.predictive_alerts a
        LEFT JOIN raw.admissions adm ON a.admission_id = adm.admission_id
        WHERE a.is_acknowledged = FALSE
        ORDER BY a.risk_score DESC, a.created_at DESC
        LIMIT :limit
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"limit": limit}).mappings().all()
    return pd.DataFrame([dict(r) for r in rows])


def acknowledge_alert(alert_id: int) -> bool:
    """Mark an alert as acknowledged."""
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                UPDATE analytics.predictive_alerts
                SET is_acknowledged = TRUE
                WHERE alert_id = :alert_id AND is_acknowledged = FALSE
            """),
            {"alert_id": alert_id},
        )
    return result.rowcount > 0


def alert_count_by_severity() -> dict[str, int]:
    """Count active alerts grouped by severity."""
    query = text("""
        SELECT severity, COUNT(*) AS count
        FROM analytics.predictive_alerts
        WHERE is_acknowledged = FALSE
        GROUP BY severity
    """)
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return {row["severity"]: row["count"] for row in rows}
