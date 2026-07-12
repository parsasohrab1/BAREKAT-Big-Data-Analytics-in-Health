"""Patient data endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from barekat.security.rbac import require_permission
from barekat.storage.database import engine

router = APIRouter()


@router.get("/")
def list_patients(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_permission("read")),
):
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM raw.patients")).scalar()
        rows = conn.execute(
            text("SELECT * FROM raw.patients ORDER BY patient_id LIMIT :limit OFFSET :offset"),
            {"limit": limit, "offset": offset},
        ).mappings().all()
    return {"total": total, "limit": limit, "offset": offset, "data": [dict(r) for r in rows]}


@router.get("/{patient_id}")
def get_patient(patient_id: str, user: dict = Depends(require_permission("view_phi"))):
    with engine.connect() as conn:
        patient = conn.execute(
            text("SELECT * FROM raw.patients WHERE patient_id = :id"),
            {"id": patient_id},
        ).mappings().first()
        if not patient:
            return {"error": "Patient not found"}

        admissions = conn.execute(
            text("SELECT * FROM raw.admissions WHERE patient_id = :id ORDER BY admission_date DESC"),
            {"id": patient_id},
        ).mappings().all()

    return {"patient": dict(patient), "admissions": [dict(a) for a in admissions]}


@router.get("/{patient_id}/admissions")
def get_patient_admissions(patient_id: str, user: dict = Depends(require_permission("read"))):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM raw.admissions WHERE patient_id = :id ORDER BY admission_date DESC"),
            {"id": patient_id},
        ).mappings().all()
    return {"patient_id": patient_id, "admissions": [dict(r) for r in rows]}
