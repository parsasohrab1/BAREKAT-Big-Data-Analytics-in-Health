"""Observability API — drift status and metrics health."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from barekat.observability.drift import check_all_models, check_model_drift
from barekat.security.rbac import require_permission, require_role, Role

router = APIRouter()


@router.get("/drift")
def drift_status(user: dict = Depends(require_role(Role.ADMIN, Role.RESEARCHER))):
    return {"models": check_all_models()}


@router.post("/drift/check/{model_name}")
def trigger_drift_check(model_name: str, user: dict = Depends(require_role(Role.ADMIN))):
    return check_model_drift(model_name)


@router.get("/health")
def observability_health(user: dict = Depends(require_permission("read"))):
    from barekat.etl.run_logger import get_recent_runs

    etl_runs = get_recent_runs(limit=5)
    drift = check_all_models()
    return {
        "etl_recent": etl_runs,
        "drift": drift,
        "drift_alerts": [d for d in drift if d.get("drift_detected")],
    }


@router.post("/alerts/webhook")
async def alertmanager_webhook(payload: dict):
    """Receive Prometheus Alertmanager notifications (internal network)."""
    import structlog
    from barekat.services.notifications import dispatch_critical_alert

    logger = structlog.get_logger(__name__)
    alerts = payload.get("alerts", [])
    for alert in alerts:
        labels = alert.get("labels", {})
        name = labels.get("alertname", "unknown")
        severity = labels.get("severity", "warning")
        status = alert.get("status", "firing")
        logger.warning("alertmanager_webhook", alertname=name, severity=severity, status=status)

        if status == "firing" and severity in ("critical", "warning"):
            if name in ("ETLJobFailed", "ModelDriftDetected"):
                dispatch_critical_alert({
                    "severity": "critical" if severity == "critical" else "high",
                    "alert_type": name,
                    "patient_id": "N/A",
                    "admission_id": "",
                    "message": alert.get("annotations", {}).get("description", name),
                    "risk_score": 1.0 if severity == "critical" else 0.8,
                })

    return {"status": "received", "count": len(alerts)}
