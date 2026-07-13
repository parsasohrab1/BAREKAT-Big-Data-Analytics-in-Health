"""Hospital system FHIR connectors — Iranian and international."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from barekat.interop.fhir.client import create_client_for_profile
from barekat.interop.fhir.parser import FHIRParser
from barekat.interop.fhir.profiles import FHIRProfile, get_profile, list_profiles
from barekat.interop.fhir.normalizer import map_to_raw_records
from barekat.streaming.models import normalize_fhir_events


@dataclass
class SyncResult:
    profile_key: str
    resources_fetched: dict[str, int] = field(default_factory=dict)
    events_parsed: int = 0
    raw_records: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    connection: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class HospitalFHIRConnector:
    """Pull FHIR R4 resources from external hospital systems."""

    RESOURCE_TYPES = ("Patient", "Encounter", "Observation", "Condition")

    def __init__(self, profile_key: str, base_url: str | None = None, token: str | None = None) -> None:
        self.profile_key = profile_key
        self.profile: FHIRProfile | None = get_profile(profile_key)
        if not self.profile:
            raise ValueError(f"Unknown connector profile: {profile_key}")
        self.client = create_client_for_profile(profile_key, base_url=base_url, token=token)
        self.parser = FHIRParser()

    def test_connection(self) -> dict[str, Any]:
        result = self.client.test_connection()
        result["profile"] = self.profile_key
        result["profile_name"] = self.profile.name if self.profile else ""
        result["region"] = self.profile.region if self.profile else ""
        return result

    def sync(
        self,
        *,
        patient_id: str | None = None,
        national_id: str | None = None,
        count_per_resource: int = 20,
    ) -> SyncResult:
        result = SyncResult(profile_key=self.profile_key)
        result.connection = self.test_connection()
        if result.connection.get("status") != "connected":
            result.errors.append(result.connection.get("message", "Connection failed"))
            return result

        search_params = self._build_search_params(patient_id=patient_id, national_id=national_id)
        all_events: list[dict[str, Any]] = []

        for resource_type in self.RESOURCE_TYPES:
            try:
                bundle = self.client.search(resource_type, {**search_params, "_count": str(count_per_resource)})
                entries = bundle.get("entry", [])
                result.resources_fetched[resource_type] = len(entries)
                parsed = self.parser.parse(bundle, profile_key=self.profile_key)
                all_events.extend(parsed)
            except Exception as exc:
                result.errors.append(f"{resource_type}: {exc}")

        result.events_parsed = len(all_events)
        normalized = normalize_fhir_events(all_events)
        result.events = normalized
        result.raw_records = map_to_raw_records(all_events)
        return result

    def fetch_patient_bundle(self, patient_fhir_id: str) -> list[dict[str, Any]]:
        """Fetch all supported resources for a single patient."""
        events: list[dict[str, Any]] = []
        for resource_type in self.RESOURCE_TYPES:
            try:
                bundle = self.client.search(resource_type, {"patient": patient_fhir_id, "_count": "50"})
                events.extend(self.parser.parse(bundle, profile_key=self.profile_key))
            except Exception:
                continue
        return normalize_fhir_events(events)

    def _build_search_params(self, patient_id: str | None, national_id: str | None) -> dict[str, str]:
        if patient_id:
            return {"patient": patient_id}
        if national_id and self.profile:
            for ident in self.profile.identifier_systems:
                if "national" in ident.system.lower() or "salamat" in ident.system.lower():
                    return {"identifier": f"{ident.system}|{national_id}"}
            return {"identifier": national_id}
        return {"_count": "20"}

    def close(self) -> None:
        self.client.close()


def get_connector(profile_key: str, base_url: str | None = None, token: str | None = None) -> HospitalFHIRConnector:
    return HospitalFHIRConnector(profile_key, base_url=base_url, token=token)


def list_connector_profiles(region: str | None = None) -> list[dict[str, Any]]:
    return list_profiles(region=region)
