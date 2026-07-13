"""Anonymization and pseudonymization for health data."""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any

from sqlalchemy import text

from barekat.config.settings import get_settings
from barekat.security.audit import log_access
from barekat.storage.database import engine


def _pseudonym_for(patient_id: str) -> str:
    settings = get_settings()
    digest = hmac.new(
        settings.pseudonymization_salt.encode(),
        patient_id.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"PSN-{digest[:16].upper()}"


def _has_legal_hold(patient_id: str, data_category: str | None = None) -> bool:
    conditions = ["patient_id = :patient_id", "is_active = TRUE"]
    params: dict[str, Any] = {"patient_id": patient_id}
    if data_category:
        conditions.append("(data_category IS NULL OR data_category = :category)")
        params["category"] = data_category
    query = text(f"""
        SELECT COUNT(*) FROM audit.legal_holds
        WHERE {' AND '.join(conditions)}
    """)
    with engine.connect() as conn:
        count = conn.execute(query, params).scalar() or 0
    return count > 0


def pseudonymize_patient(patient_id: str, *, actor: str) -> dict[str, Any]:
    if _has_legal_hold(patient_id):
        raise ValueError(f"Legal hold active for patient {patient_id}")

    pseudonym = _pseudonym_for(patient_id)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO audit.pseudonym_map (patient_id, pseudonym_id, created_by)
            VALUES (:patient_id, :pseudonym_id, :actor)
            ON CONFLICT (patient_id) DO UPDATE
            SET pseudonym_id = EXCLUDED.pseudonym_id, created_by = EXCLUDED.created_by
        """), {"patient_id": patient_id, "pseudonym_id": pseudonym, "actor": actor})

        conn.execute(text("""
            INSERT INTO audit.anonymization_status (patient_id, status, method, processed_by)
            VALUES (:patient_id, 'pseudonymized', 'HMAC-SHA256', :actor)
            ON CONFLICT (patient_id) DO UPDATE
            SET status = 'pseudonymized', method = 'HMAC-SHA256',
                processed_at = NOW(), processed_by = EXCLUDED.processed_by
        """), {"patient_id": patient_id, "actor": actor})

    log_access(
        action="pseudonymize",
        resource=f"patient:{patient_id}",
        username=actor,
        patient_id=patient_id,
        resource_type="privacy",
        details={"pseudonym_id": pseudonym},
    )
    return {"patient_id": patient_id, "pseudonym_id": pseudonym, "status": "pseudonymized"}


def anonymize_patient(patient_id: str, *, actor: str) -> dict[str, Any]:
    """Irreversible anonymization — removes direct identifiers, generalizes quasi-identifiers."""
    if _has_legal_hold(patient_id):
        raise ValueError(f"Legal hold active for patient {patient_id}")

    pseudonym = _pseudonym_for(patient_id)
    affected: dict[str, int] = {}

    with engine.begin() as conn:
        # Generalize age to decade, remove quasi-identifiers
        r = conn.execute(text("""
            UPDATE raw.patients SET
                patient_id = :pseudonym,
                age = (age / 10) * 10,
                bmi = NULL,
                smoking_status = NULL,
                updated_at = NOW()
            WHERE patient_id = :patient_id
        """), {"patient_id": patient_id, "pseudonym": pseudonym})
        affected["patients"] = r.rowcount or 0

        for table, col in [
            ("admissions", "patient_id"),
            ("dicom_studies", "patient_id"),
        ]:
            r = conn.execute(
                text(f"UPDATE raw.{table} SET {col} = :pseudonym WHERE {col} = :patient_id"),
                {"patient_id": patient_id, "pseudonym": pseudonym},
            )
            affected[table] = r.rowcount or 0

        # Redact clinical note text
        r = conn.execute(text("""
            UPDATE raw.clinical_notes SET note_text = '[REDACTED — anonymized]'
            WHERE admission_id IN (
                SELECT admission_id FROM raw.admissions WHERE patient_id = :pseudonym
            )
        """), {"pseudonym": pseudonym})
        affected["clinical_notes"] = r.rowcount or 0

        conn.execute(text("""
            INSERT INTO audit.anonymization_status (patient_id, status, method, processed_by)
            VALUES (:pseudonym, 'anonymized', 'generalization+redaction', :actor)
            ON CONFLICT (patient_id) DO UPDATE
            SET status = 'anonymized', method = 'generalization+redaction',
                processed_at = NOW(), processed_by = EXCLUDED.processed_by
        """), {"pseudonym": pseudonym, "actor": actor})

        conn.execute(text("DELETE FROM audit.pseudonym_map WHERE patient_id = :patient_id"), {
            "patient_id": patient_id,
        })

    log_access(
        action="anonymize",
        resource=f"patient:{patient_id}",
        username=actor,
        patient_id=pseudonym,
        resource_type="privacy",
        details={"affected": affected},
    )
    return {"original_id": patient_id, "anonymized_id": pseudonym, "affected": affected, "status": "anonymized"}


def erase_patient(patient_id: str, *, actor: str) -> dict[str, Any]:
    """GDPR Art. 17 — right to erasure. Cascading delete of patient data."""
    if _has_legal_hold(patient_id):
        raise ValueError(f"Legal hold active for patient {patient_id}")

    affected: dict[str, int] = {}
    with engine.begin() as conn:
        admission_ids = [
            row[0]
            for row in conn.execute(
                text("SELECT admission_id FROM raw.admissions WHERE patient_id = :id"),
                {"id": patient_id},
            ).fetchall()
        ]

        child_tables = [
            "diagnoses", "medications", "lab_results", "clinical_notes", "vital_signs",
        ]
        for table in child_tables:
            if admission_ids:
                r = conn.execute(
                    text(f"DELETE FROM raw.{table} WHERE admission_id = ANY(:ids)"),
                    {"ids": admission_ids},
                )
                affected[table] = r.rowcount or 0

        for table, col in [
            ("admissions", "patient_id"),
            ("dicom_studies", "patient_id"),
            ("analytics.admission_summary", "patient_id"),
            ("analytics.predictive_alerts", "patient_id"),
            ("audit.consent_records", "patient_id"),
            ("audit.pseudonym_map", "patient_id"),
            ("audit.anonymization_status", "patient_id"),
        ]:
            r = conn.execute(
                text(f"DELETE FROM {table} WHERE {col} = :id"),
                {"id": patient_id},
            )
            affected[table.replace(".", "_")] = r.rowcount or 0

        r = conn.execute(text("DELETE FROM raw.patients WHERE patient_id = :id"), {"id": patient_id})
        affected["patients"] = r.rowcount or 0

        conn.execute(text("""
            INSERT INTO audit.anonymization_status (patient_id, status, method, processed_by)
            VALUES (:patient_id, 'erased', 'cascade_delete', :actor)
            ON CONFLICT (patient_id) DO UPDATE
            SET status = 'erased', method = 'cascade_delete',
                processed_at = NOW(), processed_by = EXCLUDED.processed_by
        """), {"patient_id": patient_id, "actor": actor})

    log_access(
        action="erasure",
        resource=f"patient:{patient_id}",
        username=actor,
        patient_id=patient_id,
        resource_type="privacy",
        details={"affected": affected},
    )
    return {"patient_id": patient_id, "affected": affected, "status": "erased"}


def deidentify_for_export(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """HIPAA Safe Harbor — remove 18 identifier categories from export."""
    phi_fields = {
        "patient_name", "name", "address", "phone", "email", "fax",
        "ssn", "national_id", "medical_record_number", "health_plan_id",
        "account_number", "certificate_number", "vehicle_id", "device_id",
        "url", "ip_address", "biometric", "photo", "note_text",
    }
    date_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")

    result = []
    for record in records:
        clean = {}
        for key, value in record.items():
            if key.lower() in phi_fields:
                continue
            if isinstance(value, str) and date_pattern.search(value):
                clean[key] = "[DATE_REDACTED]"
            elif key == "patient_id" and value:
                clean[key] = _pseudonym_for(str(value))
            elif key == "age" and isinstance(value, (int, float)):
                clean[key] = int(value // 10) * 10
            else:
                clean[key] = value
        result.append(clean)
    return result


def get_anonymization_status(patient_id: str) -> dict[str, Any] | None:
    query = text("""
        SELECT patient_id, status, method, processed_at, processed_by
        FROM audit.anonymization_status WHERE patient_id = :id
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"id": patient_id}).mappings().first()
    return dict(row) if row else None
