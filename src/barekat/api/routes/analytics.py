"""Analytics and reporting endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from barekat.security.rbac import require_permission, require_role, Role
from barekat.storage.database import engine

router = APIRouter()


@router.get("/summary")
def analytics_summary(user: dict = Depends(require_permission("read"))):
    with engine.connect() as conn:
        stats = {
            "total_patients": conn.execute(text("SELECT COUNT(*) FROM raw.patients")).scalar() or 0,
            "total_admissions": conn.execute(text("SELECT COUNT(*) FROM raw.admissions")).scalar() or 0,
            "total_diagnoses": conn.execute(text("SELECT COUNT(*) FROM raw.diagnoses")).scalar() or 0,
            "readmission_rate": conn.execute(text(
                "SELECT ROUND(AVG(CASE WHEN readmission_flag THEN 1.0 ELSE 0.0 END)::numeric, 4) FROM raw.admissions"
            )).scalar() or 0,
            "avg_length_of_stay": conn.execute(text(
                "SELECT ROUND(AVG(length_of_stay)::numeric, 2) FROM raw.admissions"
            )).scalar() or 0,
        }

        dept_breakdown = conn.execute(text("""
            SELECT department, COUNT(*) as count
            FROM raw.admissions GROUP BY department ORDER BY count DESC
        """)).mappings().all()

    return {"summary": stats, "departments": [dict(d) for d in dept_breakdown]}


@router.get("/alerts")
def list_alerts(user: dict = Depends(require_permission("read"))):
    from barekat.services.alerts import load_active_alerts

    alerts_df = load_active_alerts()
    return {"alerts": alerts_df.to_dict(orient="records")}


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert_endpoint(alert_id: int, user: dict = Depends(require_permission("acknowledge_alerts"))):
    from barekat.services.alerts import acknowledge_alert

    if acknowledge_alert(alert_id):
        return {"status": "acknowledged", "alert_id": alert_id}
    return {"status": "not_found", "alert_id": alert_id}


@router.post("/etl/run")
def run_etl(mode: str = Query("incremental"), user: dict = Depends(require_role(Role.ADMIN))):
    from barekat.etl.pipeline import ETLPipeline

    if mode not in ("incremental", "full"):
        return {"status": "error", "message": "mode must be incremental or full"}

    pipeline = ETLPipeline()
    result = pipeline.run(mode=mode)
    return {"status": "completed", **result}


@router.get("/etl/runs")
def list_etl_runs(limit: int = 20, user: dict = Depends(require_role(Role.ADMIN))):
    from barekat.etl.run_logger import get_recent_runs

    return {"runs": get_recent_runs(limit=limit)}


@router.post("/ml/train")
def train_models_legacy(user: dict = Depends(require_role(Role.ADMIN, Role.RESEARCHER))):
    """Legacy endpoint — prefer POST /api/v1/ml/train."""
    from barekat.ml.pipeline import MLPipeline

    ml = MLPipeline()
    results = ml.run_all()
    return {"status": "completed", "results": results}
