"""Rule-based real-time alert detection from streaming events."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def detect_alerts(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate a normalized health event and return zero or more alerts."""
    alerts: list[dict[str, Any]] = []
    payload = event.get("payload", {})
    patient_id = event.get("patient_id", "unknown")
    admission_id = event.get("admission_id", "")

    vitals = payload.get("vitals", [])
    if payload.get("vital_key"):
        vitals = [{"key": payload["vital_key"], "value": payload.get("value")}]

    for vital in vitals:
        alert = _check_vital_threshold(vital, patient_id, admission_id, event)
        if alert:
            alerts.append(alert)

    if event.get("event_type", "").endswith("admission") and payload.get("admission_type") == "E":
        alerts.append(_make_alert(
            patient_id, admission_id, "stream_admission",
            "medium", "Emergency admission received via streaming ingest",
            0.55, event,
        ))

    if event.get("event_type") == "fhir.condition":
        alert = _check_condition_alert(payload, patient_id, admission_id, event)
        if alert:
            alerts.append(alert)

    return alerts


CRITICAL_CONDITIONS = {
    "A41.9", "R65.21", "I21", "I46", "J96", "N17",  # sepsis, MI, cardiac arrest, resp failure, AKI
    "C34", "C50",  # malignancy prefixes
}


def _check_condition_alert(
    payload: dict[str, Any],
    patient_id: str,
    admission_id: str,
    event: dict[str, Any],
) -> dict[str, Any] | None:
    icd = str(payload.get("icd_code", ""))
    status = payload.get("clinical_status", "active")
    if status not in ("active", "recurrence"):
        return None

    severity_code = payload.get("severity", "")
    if severity_code in ("severe", "24484000"):
        return _make_alert(
            patient_id, admission_id, "condition_alert", "critical",
            f"Severe condition detected: {payload.get('diagnosis_description', icd)}",
            0.85, event,
        )

    for prefix in CRITICAL_CONDITIONS:
        if icd.startswith(prefix):
            return _make_alert(
                patient_id, admission_id, "condition_alert", "high",
                f"Critical diagnosis via FHIR Condition: {payload.get('diagnosis_description', icd)}",
                0.72, event,
            )
    return None


def _check_vital_threshold(
    vital: dict[str, Any],
    patient_id: str,
    admission_id: str,
    event: dict[str, Any],
) -> dict[str, Any] | None:
    key = str(vital.get("key", "")).lower()
    try:
        value = float(vital.get("value"))
    except (TypeError, ValueError):
        return None

    rules = {
        "heart_rate": [(140, "critical", 0.9, "Tachycardia"), (120, "high", 0.75, "Elevated heart rate")],
        "respiratory_rate": [(28, "critical", 0.88, "Tachypnea"), (22, "high", 0.7, "Elevated respiratory rate")],
        "temperature_c": [(39.5, "critical", 0.87, "High fever"), (38.5, "high", 0.68, "Fever")],
        "lactate": [(4.0, "critical", 0.9, "Elevated lactate — sepsis risk"), (2.0, "high", 0.7, "Borderline lactate")],
    }

    if key == "systolic_bp":
        if value >= 180:
            return _make_alert(patient_id, admission_id, "vitals_deterioration", "critical", "Hypertensive crisis", 0.85, event)
        if value <= 90:
            return _make_alert(patient_id, admission_id, "vitals_deterioration", "critical", "Hypotension", 0.82, event)
        if value >= 160:
            return _make_alert(patient_id, admission_id, "vitals_deterioration", "high", "Elevated blood pressure", 0.72, event)
        return None

    if key == "spo2":
        if value <= 88:
            return _make_alert(patient_id, admission_id, "vitals_deterioration", "critical", "Critical hypoxemia", 0.92, event)
        if value <= 92:
            return _make_alert(patient_id, admission_id, "vitals_deterioration", "high", "Low SpO2", 0.78, event)
        return None

    if key not in rules:
        return None

    for threshold, severity, score, message in rules[key]:
        if value >= threshold:
            return _make_alert(patient_id, admission_id, "vitals_deterioration", severity, message, score, event)
    return None


def _make_alert(
    patient_id: str,
    admission_id: str,
    alert_type: str,
    severity: str,
    message: str,
    risk_score: float,
    event: dict[str, Any],
) -> dict[str, Any]:
    return {
        "alert_id": str(uuid.uuid4()),
        "patient_id": patient_id,
        "admission_id": admission_id or event.get("admission_id", ""),
        "alert_type": alert_type,
        "severity": severity,
        "message": message,
        "risk_score": round(risk_score, 4),
        "source_event_id": event.get("event_id"),
        "source": event.get("source"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
