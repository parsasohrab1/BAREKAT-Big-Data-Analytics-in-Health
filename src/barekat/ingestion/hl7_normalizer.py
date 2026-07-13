"""Normalize HL7 messages into canonical streaming events."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from barekat.ingestion.hl7_parser import HL7Parser


def normalize_hl7(raw_message: str) -> dict[str, Any]:
    parser = HL7Parser()
    if not parser.validate(raw_message):
        raise ValueError("Invalid HL7 message")

    message = parser.parse(raw_message)
    event: dict[str, Any] = {
        "event_id": str(uuid.uuid4()),
        "source": "hl7",
        "event_type": message.message_type or "HL7",
        "patient_id": message.patient_id or "unknown",
        "admission_id": "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {},
    }

    for seg in message.segments:
        if seg.name == "PV1" and seg.fields:
            event["admission_id"] = seg.fields[18].split("^")[0] if len(seg.fields) > 18 else ""
            event["payload"]["department"] = seg.fields[2] if len(seg.fields) > 2 else ""
            event["payload"]["admission_type"] = seg.fields[4] if len(seg.fields) > 4 else ""
        if seg.name == "OBX":
            vital = _parse_obx(seg.fields)
            if vital:
                event["payload"].setdefault("vitals", []).append(vital)

    if message.message_type.startswith("ORU"):
        event["event_type"] = "hl7.lab_result"
    elif message.message_type.startswith("ADT"):
        event["event_type"] = "hl7.admission"

    return event


def _parse_obx(fields: list[str]) -> dict[str, Any] | None:
    if len(fields) < 6:
        return None
    identifier = fields[2].split("^")[0] if fields[2] else ""
    value = fields[4] if len(fields) > 4 else ""
    unit = fields[5] if len(fields) > 5 else ""

    vital_names = {
        "8867-4": "heart_rate",
        "HR": "heart_rate",
        "9279-1": "respiratory_rate",
        "RR": "respiratory_rate",
        "8480-6": "systolic_bp",
        "8462-4": "diastolic_bp",
        "8310-5": "temperature_c",
        "TEMP": "temperature_c",
        "2708-6": "spo2",
        "SPO2": "spo2",
        "2524-7": "lactate",
    }
    key = vital_names.get(identifier, identifier.lower())
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = value

    return {"key": key, "value": numeric, "unit": unit}
