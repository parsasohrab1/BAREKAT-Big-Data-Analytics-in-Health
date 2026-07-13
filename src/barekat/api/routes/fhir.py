"""FHIR R4 interoperability API — profiles, connectors, bundle ingest."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from barekat.interop.fhir.connectors import get_connector, list_connector_profiles
from barekat.interop.fhir.parser import FHIRParser
from barekat.interop.fhir.normalizer import map_to_raw_records
from barekat.security.rbac import require_permission, require_role, Role
from barekat.services.fhir_sync import log_sync_run, persist_raw_records
from barekat.storage.kafka_client import EventProducer
from barekat.streaming.models import normalize_fhir_events

router = APIRouter()

SUPPORTED_RESOURCES = ["Patient", "Encounter", "Observation", "Condition"]


class FHIRBundleRequest(BaseModel):
    bundle: dict[str, Any]
    profile: str | None = Field(None, description="Connector profile key (iran_moh, international_hapi, ...)")
    persist: bool = Field(False, description="Persist mapped records to PostgreSQL raw schema")
    stream: bool = Field(True, description="Publish events to Kafka")


class ConnectorTestRequest(BaseModel):
    profile: str
    base_url: str | None = None
    token: str | None = None


class ConnectorSyncRequest(BaseModel):
    profile: str
    base_url: str | None = None
    token: str | None = None
    patient_id: str | None = None
    national_id: str | None = Field(None, description="کد ملی — Iranian national ID")
    persist: bool = False
    stream: bool = True
    count_per_resource: int = Field(20, ge=1, le=100)


@router.get("/capabilities")
def fhir_capabilities():
    return {
        "fhir_version": "R4",
        "supported_resources": SUPPORTED_RESOURCES,
        "profiles": list_connector_profiles(),
        "regions": {
            "IR": list_connector_profiles(region="IR"),
            "INT": list_connector_profiles(region="INT"),
        },
        "ingest_endpoints": {
            "bundle": "POST /api/v1/fhir/bundle",
            "legacy": "POST /api/v1/ingest/fhir",
        },
    }


@router.get("/profiles")
def list_profiles(region: str | None = Query(None, pattern="^(IR|INT)$")):
    return {"profiles": list_connector_profiles(region=region)}


@router.get("/profiles/{profile_key}")
def get_profile_detail(profile_key: str):
    profiles = {p["key"]: p for p in list_connector_profiles()}
    if profile_key not in profiles:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profiles[profile_key]


@router.post("/bundle")
def ingest_fhir_bundle(body: FHIRBundleRequest, user: dict = Depends(require_permission("write"))):
    parser = FHIRParser()
    if not parser.validate(body.bundle):
        raise HTTPException(status_code=400, detail="Invalid FHIR Bundle or unsupported resources")

    parsed = parser.parse(body.bundle, profile_key=body.profile)
    if not parsed:
        raise HTTPException(status_code=400, detail="No Patient/Encounter/Observation/Condition found in bundle")

    events = normalize_fhir_events(parsed)
    raw_records = map_to_raw_records(parsed)

    if body.stream:
        producer = EventProducer()
        for event in events:
            producer.publish_fhir(event)
            producer.publish_raw_event(event)

    persisted = 0
    if body.persist:
        persisted = persist_raw_records(raw_records)

    return {
        "status": "accepted",
        "profile": body.profile,
        "resources_parsed": {r: sum(1 for p in parsed if p.get("resource_type") == r) for r in SUPPORTED_RESOURCES},
        "events": len(events),
        "raw_records": {k: len(v) for k, v in raw_records.items()},
        "persisted_rows": persisted,
    }


@router.post("/connectors/test")
def test_connector(body: ConnectorTestRequest, user: dict = Depends(require_permission("read"))):
    try:
        connector = get_connector(body.profile, base_url=body.base_url, token=body.token)
        result = connector.test_connection()
        connector.close()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/connectors/sync")
def sync_connector(body: ConnectorSyncRequest, user: dict = Depends(require_role(Role.ADMIN, Role.CLINICIAN))):
    try:
        connector = get_connector(body.profile, base_url=body.base_url, token=body.token)
        sync_result = connector.sync(
            patient_id=body.patient_id,
            national_id=body.national_id,
            count_per_resource=body.count_per_resource,
        )
        connector.close()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    persisted = 0
    if body.persist and sync_result.raw_records:
        persisted = persist_raw_records(sync_result.raw_records)

    if body.stream and sync_result.events:
        producer = EventProducer()
        for event in sync_result.events:
            producer.publish_fhir(event)
            producer.publish_raw_event(event)

    log_sync_run(
        profile_key=body.profile,
        status="success" if not sync_result.errors else "partial",
        resources_fetched=sync_result.resources_fetched,
        events_parsed=sync_result.events_parsed,
        errors=sync_result.errors,
    )

    return {
        "status": "completed" if not sync_result.errors else "partial",
        "profile": body.profile,
        "connection": sync_result.connection,
        "resources_fetched": sync_result.resources_fetched,
        "events_parsed": sync_result.events_parsed,
        "raw_records": {k: len(v) for k, v in sync_result.raw_records.items()},
        "persisted_rows": persisted,
        "errors": sync_result.errors,
    }
