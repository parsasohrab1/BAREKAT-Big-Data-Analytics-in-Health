"""Data retention policies and automatic purge."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from barekat.config.settings import get_settings
from barekat.security.audit import log_access, purge_old_access_logs
from barekat.storage.database import engine

# Maps data_category → (schema.table, date_column)
RETENTION_TARGETS: dict[str, tuple[str, str]] = {
    "clinical_notes": ("raw.clinical_notes", "created_at"),
    "lab_results": ("raw.lab_results", "created_at"),
    "admissions": ("raw.admissions", "created_at"),
    "dicom_studies": ("raw.dicom_studies", "retrieved_at"),
    "predictive_alerts": ("analytics.predictive_alerts", "created_at"),
}


def get_retention_policies() -> list[dict[str, Any]]:
    query = text("""
        SELECT policy_id, data_category, retention_days, regulation_ref,
               auto_purge, description_fa, updated_at
        FROM audit.retention_policies
        ORDER BY data_category
    """)
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [dict(r) for r in rows]


def _start_deletion_job(job_type: str, triggered_by: str) -> int:
    query = text("""
        INSERT INTO audit.deletion_jobs (job_type, status, triggered_by)
        VALUES (:job_type, 'running', :triggered_by)
        RETURNING job_id
    """)
    with engine.begin() as conn:
        job_id = conn.execute(query, {"job_type": job_type, "triggered_by": triggered_by}).scalar()
    return int(job_id)


def _finish_deletion_job(job_id: int, status: str, affected: dict, error: str | None = None) -> None:
    query = text("""
        UPDATE audit.deletion_jobs
        SET status = :status, records_affected = CAST(:affected AS JSONB),
            error_message = :error, finished_at = :finished_at
        WHERE job_id = :job_id
    """)
    with engine.begin() as conn:
        conn.execute(query, {
            "job_id": job_id,
            "status": status,
            "affected": json.dumps(affected),
            "error": error,
            "finished_at": datetime.now(timezone.utc),
        })


def _patients_on_hold() -> set[str]:
    query = text("""
        SELECT DISTINCT patient_id FROM audit.legal_holds
        WHERE is_active = TRUE AND patient_id IS NOT NULL
    """)
    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()
    return {r[0] for r in rows}


def purge_expired_data(*, triggered_by: str = "system") -> dict[str, Any]:
    """Delete records past retention period. Respects legal holds."""
    settings = get_settings()
    if not settings.data_retention_enabled:
        return {"status": "skipped", "reason": "retention disabled"}

    job_id = _start_deletion_job("retention_purge", triggered_by)
    affected: dict[str, int] = {}
    held = _patients_on_hold()

    try:
        policies = get_retention_policies()
        for policy in policies:
            if not policy["auto_purge"]:
                continue

            category = policy["data_category"]
            days = policy["retention_days"]

            if category == "access_logs":
                affected["access_logs"] = purge_old_access_logs(days)
                continue

            target = RETENTION_TARGETS.get(category)
            if not target:
                continue

            table, date_col = target

            if held and category in ("admissions", "clinical_notes", "lab_results", "dicom_studies"):
                held_list = list(held)
                if category == "admissions":
                    query = text(f"""
                        DELETE FROM {table}
                        WHERE {date_col} < NOW() - (:days || ' days')::INTERVAL
                          AND patient_id != ALL(:held)
                    """)
                    params = {"days": days, "held": held_list}
                elif category in ("clinical_notes", "lab_results"):
                    query = text(f"""
                        DELETE FROM {table}
                        WHERE {date_col} < NOW() - (:days || ' days')::INTERVAL
                          AND admission_id NOT IN (
                              SELECT admission_id FROM raw.admissions WHERE patient_id = ANY(:held)
                          )
                    """)
                    params = {"days": days, "held": held_list}
                elif category == "dicom_studies":
                    query = text(f"""
                        DELETE FROM {table}
                        WHERE {date_col} < NOW() - (:days || ' days')::INTERVAL
                          AND (patient_id IS NULL OR patient_id != ALL(:held))
                    """)
                    params = {"days": days, "held": held_list}
                else:
                    query = text(f"""
                        DELETE FROM {table}
                        WHERE {date_col} < NOW() - (:days || ' days')::INTERVAL
                    """)
                    params = {"days": days}
            else:
                query = text(f"""
                    DELETE FROM {table}
                    WHERE {date_col} < NOW() - (:days || ' days')::INTERVAL
                """)
                params = {"days": days}

            with engine.begin() as conn:
                result = conn.execute(query, params)
                affected[category] = result.rowcount or 0

        _finish_deletion_job(job_id, "success", affected)
        log_access(
            action="retention_purge",
            resource="system/retention",
            username=triggered_by,
            resource_type="privacy",
            details={"affected": affected, "job_id": job_id},
        )
        return {"status": "success", "job_id": job_id, "affected": affected}

    except Exception as exc:
        _finish_deletion_job(job_id, "failed", affected, str(exc))
        raise


def get_deletion_jobs(limit: int = 20) -> list[dict[str, Any]]:
    query = text("""
        SELECT job_id, job_type, status, triggered_by, records_affected,
               error_message, started_at, finished_at
        FROM audit.deletion_jobs
        ORDER BY started_at DESC
        LIMIT :limit
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"limit": limit}).mappings().all()
    return [dict(r) for r in rows]


def place_legal_hold(
    *,
    patient_id: str | None,
    data_category: str | None,
    reason: str,
    placed_by: str,
) -> dict[str, Any]:
    query = text("""
        INSERT INTO audit.legal_holds (patient_id, data_category, reason, placed_by)
        VALUES (:patient_id, :data_category, :reason, :placed_by)
        RETURNING hold_id
    """)
    with engine.begin() as conn:
        hold_id = conn.execute(query, {
            "patient_id": patient_id,
            "data_category": data_category,
            "reason": reason,
            "placed_by": placed_by,
        }).scalar()

    log_access(
        action="legal_hold_placed",
        resource=f"hold:{hold_id}",
        username=placed_by,
        patient_id=patient_id,
        resource_type="privacy",
        details={"data_category": data_category, "reason": reason},
    )
    return {"hold_id": hold_id, "patient_id": patient_id, "is_active": True}


def release_legal_hold(hold_id: int, *, released_by: str) -> dict[str, Any]:
    query = text("""
        UPDATE audit.legal_holds
        SET is_active = FALSE, released_at = NOW()
        WHERE hold_id = :hold_id AND is_active = TRUE
        RETURNING hold_id, patient_id
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {"hold_id": hold_id}).mappings().first()

    if not row:
        raise ValueError(f"Active legal hold {hold_id} not found")

    log_access(
        action="legal_hold_released",
        resource=f"hold:{hold_id}",
        username=released_by,
        patient_id=row["patient_id"],
        resource_type="privacy",
    )
    return dict(row)


def record_consent(
    *,
    patient_id: str,
    purpose: str,
    lawful_basis: str,
    granted: bool,
    recorded_by: str,
    notes: str | None = None,
) -> dict[str, Any]:
    query = text("""
        INSERT INTO audit.consent_records
            (patient_id, purpose, lawful_basis, granted, recorded_by, notes)
        VALUES (:patient_id, :purpose, :lawful_basis, :granted, :recorded_by, :notes)
        RETURNING consent_id, granted_at
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "patient_id": patient_id,
            "purpose": purpose,
            "lawful_basis": lawful_basis,
            "granted": granted,
            "recorded_by": recorded_by,
            "notes": notes,
        }).mappings().first()

    log_access(
        action="consent_recorded",
        resource=f"patient:{patient_id}",
        username=recorded_by,
        patient_id=patient_id,
        resource_type="consent",
        details={"purpose": purpose, "lawful_basis": lawful_basis, "granted": granted},
    )
    return dict(row) if row else {}
