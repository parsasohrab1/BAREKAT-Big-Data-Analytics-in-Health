"""FHIR REST client for hospital system integration."""

from __future__ import annotations

from typing import Any

import httpx

from barekat.interop.fhir.profiles import FHIRProfile, get_profile


class FHIRClient:
    """Minimal FHIR R4 REST client (read + search + capability statement)."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        profile: FHIRProfile | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.profile = profile
        headers = {"Accept": "application/fhir+json", "Content-Type": "application/fhir+json"}
        if profile:
            headers.update(profile.headers)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def capability_statement(self) -> dict[str, Any]:
        response = self._client.get("/metadata")
        response.raise_for_status()
        return response.json()

    def read(self, resource_type: str, resource_id: str) -> dict[str, Any]:
        response = self._client.get(f"/{resource_type}/{resource_id}")
        response.raise_for_status()
        return response.json()

    def search(self, resource_type: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        response = self._client.get(f"/{resource_type}", params=params or {})
        response.raise_for_status()
        return response.json()

    def test_connection(self) -> dict[str, Any]:
        try:
            meta = self.capability_statement()
            software = meta.get("software", {})
            return {
                "status": "connected",
                "fhir_version": meta.get("fhirVersion"),
                "software": software.get("name", ""),
                "publisher": meta.get("publisher", ""),
                "resource_count": len(meta.get("rest", [{}])[0].get("resource", [])),
            }
        except httpx.HTTPError as exc:
            return {"status": "error", "message": str(exc)}


def create_client_for_profile(
    profile_key: str,
    base_url: str | None = None,
    token: str | None = None,
) -> FHIRClient:
    profile = get_profile(profile_key)
    if not profile:
        raise ValueError(f"Unknown FHIR profile: {profile_key}")
    url = base_url or profile.base_url_example
    if not url:
        raise ValueError(f"No base URL configured for profile {profile_key}")
    return FHIRClient(url, token=token, profile=profile)
