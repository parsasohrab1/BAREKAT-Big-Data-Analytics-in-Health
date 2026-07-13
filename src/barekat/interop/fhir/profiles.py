"""FHIR R4 interoperability profiles — Iranian and international hospital systems."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IdentifierSystem:
    system: str
    label: str
    region: str  # IR | INT


@dataclass(frozen=True)
class FHIRProfile:
    key: str
    name: str
    region: str
    description: str
    fhir_version: str = "R4"
    base_url_example: str = ""
    supported_resources: tuple[str, ...] = ("Patient", "Encounter", "Observation", "Condition")
    identifier_systems: tuple[IdentifierSystem, ...] = field(default_factory=tuple)
    search_params: dict[str, list[str]] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


# --- Iranian identifier systems ---
IR_NATIONAL_ID = IdentifierSystem(
    system="http://fhir.salamat.org.ir/sid/national-id",
    label="کد ملی",
    region="IR",
)
IR_MEDICAL_CODE = IdentifierSystem(
    system="http://fhir.salamat.org.ir/sid/medical-code",
    label="نظام پزشکی",
    region="IR",
)
IR_SALAMAT_ID = IdentifierSystem(
    system="http://fhir.salamat.org.ir/sid/salamat-insurance",
    label="بیمه سلامت",
    region="IR",
)
IR_TAMIN_ID = IdentifierSystem(
    system="http://fhir.tamin.ir/sid/patient-id",
    label="تأمین اجتماعی",
    region="IR",
)
IR_SEPAS_ID = IdentifierSystem(
    system="http://sepas.ihio.gov.ir/fhir/sid/patient",
    label="SEPAS / IHIO",
    region="IR",
)

# --- International identifier systems ---
INT_MRN = IdentifierSystem(
    system="http://hospital.example.org/sid/mrn",
    label="Medical Record Number",
    region="INT",
)
INT_US_SSN = IdentifierSystem(
    system="http://hl7.org/fhir/sid/us-ssn",
    label="US SSN",
    region="INT",
)
INT_NHS = IdentifierSystem(
    system="https://fhir.nhs.uk/Id/nhs-number",
    label="NHS Number (UK)",
    region="INT",
)


FHIR_PROFILES: dict[str, FHIRProfile] = {
    "iran_moh": FHIRProfile(
        key="iran_moh",
        name="Iran MOH / SEPAS",
        region="IR",
        description="وزارت بهداشت — تبادل SEPAS، شناسه ملی و نظام پزشکی",
        base_url_example="https://sepas-api.example.ir/fhir",
        identifier_systems=(IR_NATIONAL_ID, IR_MEDICAL_CODE, IR_SEPAS_ID),
        search_params={
            "Patient": ["identifier", "name", "birthdate"],
            "Encounter": ["patient", "date", "class"],
            "Observation": ["patient", "category", "code", "date"],
            "Condition": ["patient", "clinical-status", "code"],
        },
    ),
    "iran_salamat": FHIRProfile(
        key="iran_salamat",
        name="Salamat Insurance",
        region="IR",
        description="بیمه سلامت ایران — FHIR R4",
        base_url_example="https://fhir.salamat.org.ir/r4",
        identifier_systems=(IR_NATIONAL_ID, IR_SALAMAT_ID),
        search_params={
            "Patient": ["identifier"],
            "Encounter": ["patient", "date"],
            "Observation": ["patient", "code"],
            "Condition": ["patient", "code"],
        },
    ),
    "iran_tamin": FHIRProfile(
        key="iran_tamin",
        name="Tamin Ejtemaee",
        region="IR",
        description="سازمان تأمین اجتماعی — FHIR",
        base_url_example="https://fhir.tamin.ir/r4",
        identifier_systems=(IR_NATIONAL_ID, IR_TAMIN_ID),
    ),
    "international_us_core": FHIRProfile(
        key="international_us_core",
        name="US Core R4",
        region="INT",
        description="HL7 US Core Implementation Guide STU6",
        base_url_example="https://hapi.fhir.org/baseR4",
        identifier_systems=(INT_MRN, INT_US_SSN),
        headers={"Accept": "application/fhir+json"},
    ),
    "international_ips": FHIRProfile(
        key="international_ips",
        name="International Patient Summary",
        region="INT",
        description="HL7 IPS — Patient, Encounter, Condition, Observation",
        base_url_example="https://hl7-ips-healthrecord.example/fhir",
        identifier_systems=(INT_MRN, INT_NHS),
    ),
    "international_epic": FHIRProfile(
        key="international_epic",
        name="Epic FHIR",
        region="INT",
        description="Epic on FHIR — SMART Backend Services",
        base_url_example="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
        identifier_systems=(INT_MRN,),
        headers={"Accept": "application/fhir+json"},
    ),
    "international_hapi": FHIRProfile(
        key="international_hapi",
        name="HAPI FHIR (Test)",
        region="INT",
        description="HAPI FHIR public test server for development",
        base_url_example="https://hapi.fhir.org/baseR4",
        identifier_systems=(INT_MRN,),
    ),
}


def get_profile(key: str) -> FHIRProfile | None:
    return FHIR_PROFILES.get(key)


def list_profiles(region: str | None = None) -> list[dict[str, Any]]:
    profiles = FHIR_PROFILES.values()
    if region:
        profiles = [p for p in profiles if p.region == region.upper()]
    return [
        {
            "key": p.key,
            "name": p.name,
            "region": p.region,
            "description": p.description,
            "fhir_version": p.fhir_version,
            "supported_resources": list(p.supported_resources),
            "identifier_systems": [{"system": i.system, "label": i.label} for i in p.identifier_systems],
            "base_url_example": p.base_url_example,
        }
        for p in profiles
    ]
