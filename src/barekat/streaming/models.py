"""Canonical health event models for streaming."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def build_event(
    *,
    source: str,
    event_type: str,
    patient_id: str,
    admission_id: str = "",
    payload: dict[str, Any] | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    return {
        "event_id": event_id or str(uuid.uuid4()),
        "source": source,
        "event_type": event_type,
        "patient_id": patient_id,
        "admission_id": admission_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload or {},
    }


def normalize_fhir_events(parsed_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for item in parsed_events:
        normalized.append(build_event(
            source="fhir",
            event_type=item.get("event_type", "fhir.unknown"),
            patient_id=item.get("patient_id", "unknown"),
            admission_id=item.get("admission_id", ""),
            payload=item.get("payload", {}),
        ))
    return normalized
