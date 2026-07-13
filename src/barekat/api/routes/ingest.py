"""Real-time HL7/FHIR ingest endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from barekat.interop.fhir.parser import FHIRParser
from barekat.ingestion.hl7_normalizer import normalize_hl7
from barekat.security.rbac import require_permission
from barekat.storage.kafka_client import EventProducer
from barekat.streaming.models import normalize_fhir_events

router = APIRouter()


class HL7IngestRequest(BaseModel):
    message: str = Field(..., min_length=10, description="Raw HL7 v2.x message")


class FHIRIngestRequest(BaseModel):
    resource: dict[str, Any]
    profile: str | None = None


@router.post("/hl7")
def ingest_hl7(body: HL7IngestRequest, user: dict = Depends(require_permission("write"))):
    try:
        event = normalize_hl7(body.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    producer = EventProducer()
    producer.publish_hl7(event)
    producer.publish_raw_event(event)
    return {"status": "accepted", "event_id": event["event_id"], "event_type": event["event_type"]}


@router.post("/fhir")
def ingest_fhir(body: FHIRIngestRequest, user: dict = Depends(require_permission("write"))):
    parser = FHIRParser()
    if not parser.validate(body.resource):
        raise HTTPException(status_code=400, detail="Invalid FHIR resource or Bundle")

    parsed = parser.parse(body.resource, profile_key=body.profile)
    events = normalize_fhir_events(parsed)
    if not events:
        raise HTTPException(status_code=400, detail="No supported FHIR resources found")

    producer = EventProducer()
    for event in events:
        producer.publish_fhir(event)
        producer.publish_raw_event(event)

    return {
        "status": "accepted",
        "events": [{"event_id": e["event_id"], "event_type": e["event_type"]} for e in events],
    }


@router.post("/hl7/raw")
async def ingest_hl7_raw(request: Request, user: dict = Depends(require_permission("write"))):
    """Accept raw HL7 body (text/plain) for MLLP-style gateways."""
    raw = (await request.body()).decode("utf-8", errors="replace")
    return ingest_hl7(HL7IngestRequest(message=raw), user)
