"""Map FHIR events to BAREKAT raw schema records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def map_to_raw_records(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Convert parsed FHIR events into raw.* table-shaped records."""
    patients: list[dict] = []
    admissions: list[dict] = []
    diagnoses: list[dict] = []
    lab_results: list[dict] = []
    seen_patients: set[str] = set()
    seen_admissions: set[str] = set()

    for event in events:
        rtype = event.get("resource_type", "")
        payload = event.get("payload", {})
        patient_id = _barekat_patient_id(event.get("patient_id", ""))

        if rtype == "Patient" and patient_id not in seen_patients:
            seen_patients.add(patient_id)
            patients.append({
                "patient_id": patient_id,
                "age": _age_from_birth(payload.get("birth_date")),
                "gender": _map_gender(payload.get("gender")),
                "blood_type": None,
                "bmi": None,
                "smoking_status": None,
                "diabetes": False,
                "hypertension": False,
            })

        elif rtype == "Encounter":
            adm_id = _barekat_admission_id(event.get("admission_id", ""))
            if adm_id not in seen_admissions:
                seen_admissions.add(adm_id)
                period = payload.get("period") or {}
                adm_date = _parse_dt(period.get("start"))
                dis_date = _parse_dt(period.get("end"))
                los = (dis_date - adm_date).days if adm_date and dis_date else None
                admissions.append({
                    "admission_id": adm_id,
                    "patient_id": patient_id,
                    "admission_date": adm_date or datetime.now(timezone.utc),
                    "discharge_date": dis_date,
                    "department": payload.get("department") or payload.get("class_display", "Unknown"),
                    "admission_type": _map_admission_type(payload.get("class_code")),
                    "length_of_stay": los or 1,
                    "icu_required": payload.get("class_code") == "ICU",
                    "readmission_flag": False,
                    "mortality_flag": False,
                    "sepsis_flag": False,
                })

        elif rtype == "Condition":
            icd = payload.get("icd_code", "UNK")
            adm_id = _barekat_admission_id(event.get("admission_id", f"AD-{patient_id}"))
            diagnoses.append({
                "diagnosis_id": f"DG-{event.get('resource_id', icd)}",
                "admission_id": adm_id,
                "icd_code": icd,
                "diagnosis_description": payload.get("diagnosis_description", ""),
                "primary_diagnosis": payload.get("clinical_status") == "active",
            })

        elif rtype == "Observation":
            adm_id = _barekat_admission_id(event.get("admission_id", f"AD-{patient_id}"))
            code = payload.get("display") or payload.get("vital_key", "observation")
            value = payload.get("value")
            if isinstance(value, dict):
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            lab_results.append({
                "lab_id": f"LB-{event.get('resource_id', code)}",
                "admission_id": adm_id,
                "test_name": code,
                "result_value": numeric,
                "unit": payload.get("unit", ""),
                "test_date": _parse_dt(payload.get("effective_datetime")) or datetime.now(timezone.utc),
                "abnormal_flag": payload.get("interpretation") in ("H", "HH", "L", "LL", "A"),
            })

    return {
        "patients": patients,
        "admissions": admissions,
        "diagnoses": diagnoses,
        "lab_results": lab_results,
    }


def _barekat_patient_id(fhir_id: str) -> str:
    if fhir_id.startswith("PT"):
        return fhir_id
    return f"PT{fhir_id[:8].upper().replace('-', '')}"


def _barekat_admission_id(fhir_id: str) -> str:
    if fhir_id.startswith("AD"):
        return fhir_id
    return f"AD{fhir_id[:8].upper().replace('-', '')}"


def _map_gender(gender: str | None) -> str:
    mapping = {"male": "M", "female": "F", "other": "O", "unknown": "O"}
    return mapping.get(str(gender or "").lower(), "O")


def _map_admission_type(class_code: str | None) -> str:
    mapping = {"EMER": "Emergency", "IMP": "Elective", "AMB": "Urgent", "ACUTE": "Emergency"}
    return mapping.get(str(class_code or "").upper(), "Elective")


def _age_from_birth(birth_date: str | None) -> int:
    if not birth_date:
        return 0
    try:
        born = datetime.fromisoformat(birth_date.replace("Z", "+00:00"))
        today = datetime.now(timezone.utc)
        return max(0, today.year - born.year - ((today.month, today.day) < (born.month, born.day)))
    except ValueError:
        return 0


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, dict):
        value = value.get("start")
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
