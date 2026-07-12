"""Analytics and reporting endpoints."""

from fastapi import APIRouter, Depends
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
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT * FROM analytics.predictive_alerts
            WHERE is_acknowledged = FALSE
            ORDER BY created_at DESC LIMIT 100
        """)).mappings().all()
    return {"alerts": [dict(r) for r in rows]}


@router.post("/etl/run")
def run_etl(user: dict = Depends(require_role(Role.ADMIN))):
    from barekat.etl.pipeline import ETLPipeline

    pipeline = ETLPipeline()
    counts = pipeline.run()
    quality = pipeline.validate_data_quality()
    return {"status": "completed", "loaded_records": counts, "quality_checks": quality}


@router.post("/ml/train")
def train_models(user: dict = Depends(require_role(Role.ADMIN, Role.RESEARCHER))):
    from barekat.etl.pipeline import ETLPipeline
    from barekat.ml.pipeline import MLPipeline
    from barekat.ingestion.csv_loader import CSVIngestor
    from pathlib import Path
    from barekat.config.settings import get_settings

    settings = get_settings()
    ingestor = CSVIngestor(Path(settings.data_raw_path))
    raw = ingestor.load_all()

    table_map = {
        "patients": "Patients", "admissions": "Admissions",
        "diagnoses": "Diagnoses", "medications": "Medications", "lab_results": "Lab_Results",
    }
    data = {table_map[k]: v for k, v in raw.items()}

    ml = MLPipeline()
    results = ml.run_all(data)
    return {"status": "completed", "results": results}
