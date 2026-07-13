"""FHIR R4 parser — Patient, Encounter, Observation, Condition."""

from __future__ import annotations

from typing import Any

from barekat.interop.fhir.profiles import (
    IR_MEDICAL_CODE,
    IR_NATIONAL_ID,
    IR_SALAMAT_ID,
    IR_SEPAS_ID,
    IR_TAMIN_ID,
)

SUPPORTED_RESOURCES = frozenset({"Patient", "Encounter", "Observation", "Condition", "Bundle"})

IR_IDENTIFIER_SYSTEMS = {
    IR_NATIONAL_ID.system,
    IR_MEDICAL_CODE.system,
    IR_SALAMAT_ID.system,
    IR_TAMIN_ID.system,
    IR_SEPAS_ID.system,
    "http://hl7.org/fhir/sid/national-id",
}


class FHIRParser:
    """Parse FHIR R4 resources into normalized event payloads."""

    def validate(self, resource: dict[str, Any]) -> bool:
        if not isinstance(resource, dict):
            return False
        rtype = resource.get("resourceType")
        if rtype == "Bundle":
            return bool(resource.get("entry"))
        return rtype in SUPPORTED_RESOURCES

    def parse(self, resource: dict[str, Any], profile_key: str | None = None) -> list[dict[str, Any]]:
        if resource.get("resourceType") == "Bundle":
            events: list[dict[str, Any]] = []
            for entry in resource.get("entry", []):
                item = entry.get("resource", {})
                events.extend(self._parse_resource(item, profile_key))
            return events
        return self._parse_resource(resource, profile_key)

    def _parse_resource(self, resource: dict[str, Any], profile_key: str | None) -> list[dict[str, Any]]:
        rtype = resource.get("resourceType", "")
        parsers = {
            "Patient": self._parse_patient,
            "Encounter": self._parse_encounter,
            "Observation": self._parse_observation,
            "Condition": self._parse_condition,
        }
        parser = parsers.get(rtype)
        if not parser:
            return []
        result = parser(resource)
        if profile_key:
            result["profile"] = profile_key
        return [result]

    def _parse_patient(self, resource: dict[str, Any]) -> dict[str, Any]:
        identifiers = self._extract_identifiers(resource.get("identifier", []))
        name_fa, name_en = self._extract_names(resource.get("name", []))
        return {
            "event_type": "fhir.patient",
            "resource_type": "Patient",
            "resource_id": resource.get("id", ""),
            "patient_id": resource.get("id", ""),
            "payload": {
                "name": name_en or name_fa,
                "name_fa": name_fa,
                "name_en": name_en,
                "gender": resource.get("gender"),
                "birth_date": resource.get("birthDate"),
                "identifiers": identifiers,
                "national_id": identifiers.get(IR_NATIONAL_ID.system) or identifiers.get("http://hl7.org/fhir/sid/national-id"),
                "active": resource.get("active", True),
                "marital_status": (resource.get("maritalStatus") or {}).get("coding", [{}])[0].get("code"),
                "address": self._extract_address(resource.get("address", [])),
            },
        }

    def _parse_encounter(self, resource: dict[str, Any]) -> dict[str, Any]:
        patient_id = self._extract_patient_id(resource)
        enc_class = resource.get("class") or {}
        dept = ""
        for loc in resource.get("location", []):
            loc_ref = (loc.get("location") or {}).get("display", "")
            if loc_ref:
                dept = loc_ref
                break
        if not dept:
            for t in resource.get("type", []):
                codings = t.get("coding", [])
                if codings:
                    dept = codings[0].get("display", codings[0].get("code", ""))
                    break

        return {
            "event_type": "fhir.encounter",
            "resource_type": "Encounter",
            "resource_id": resource.get("id", ""),
            "patient_id": patient_id,
            "admission_id": resource.get("id", ""),
            "payload": {
                "status": resource.get("status"),
                "class_code": enc_class.get("code") if isinstance(enc_class, dict) else enc_class,
                "class_display": enc_class.get("display", "") if isinstance(enc_class, dict) else "",
                "period": resource.get("period"),
                "department": dept,
                "service_provider": (resource.get("serviceProvider") or {}).get("display", ""),
                "priority": (resource.get("priority") or {}).get("coding", [{}])[0].get("code"),
                "identifiers": self._extract_identifiers(resource.get("identifier", [])),
            },
        }

    def _parse_observation(self, resource: dict[str, Any]) -> dict[str, Any]:
        code, display, system = self._extract_code(resource.get("code", {}))
        value, unit = self._extract_value(resource)
        vital_map = {
            "8867-4": "heart_rate", "9279-1": "respiratory_rate",
            "8480-6": "systolic_bp", "8462-4": "diastolic_bp",
            "8310-5": "temperature_c", "2708-6": "spo2", "2524-7": "lactate",
        }
        vital_key = vital_map.get(code, display.lower().replace(" ", "_") if display else "observation")

        return {
            "event_type": "fhir.observation",
            "resource_type": "Observation",
            "resource_id": resource.get("id", ""),
            "patient_id": self._extract_patient_id(resource),
            "admission_id": self._extract_encounter_id(resource),
            "payload": {
                "code": code,
                "code_system": system,
                "display": display,
                "vital_key": vital_key,
                "value": value,
                "unit": unit,
                "category": self._extract_category(resource.get("category", [])),
                "status": resource.get("status"),
                "effective_datetime": resource.get("effectiveDateTime") or resource.get("effectivePeriod"),
                "interpretation": self._extract_interpretation(resource),
            },
        }

    def _parse_condition(self, resource: dict[str, Any]) -> dict[str, Any]:
        code, display, system = self._extract_code(resource.get("code", {}))
        clinical_status = (resource.get("clinicalStatus") or {}).get("coding", [{}])[0].get("code", "active")
        verification = (resource.get("verificationStatus") or {}).get("coding", [{}])[0].get("code", "")

        return {
            "event_type": "fhir.condition",
            "resource_type": "Condition",
            "resource_id": resource.get("id", ""),
            "patient_id": self._extract_patient_id(resource),
            "admission_id": self._extract_encounter_id(resource),
            "payload": {
                "icd_code": code,
                "code_system": system,
                "diagnosis_description": display,
                "clinical_status": clinical_status,
                "verification_status": verification,
                "severity": self._extract_severity(resource),
                "onset_datetime": resource.get("onsetDateTime") or resource.get("onsetPeriod"),
                "recorded_date": resource.get("recordedDate"),
                "category": self._extract_category(resource.get("category", [])),
            },
        }

    def _extract_identifiers(self, identifiers: list[dict]) -> dict[str, str]:
        result = {}
        for ident in identifiers:
            system = ident.get("system", "")
            value = ident.get("value", "")
            if system and value:
                result[system] = value
        return result

    def _extract_names(self, names: list[dict]) -> tuple[str, str]:
        fa, en = "", ""
        for name in names:
            given = " ".join(name.get("given", []))
            family = name.get("family", "")
            full = f"{given} {family}".strip()
            lang = (name.get("extension") or [{}])
            use = name.get("use", "")
            if any("fa" in str(e).lower() for e in lang) or use == "official":
                fa = fa or full
            else:
                en = en or full
        if not fa and names:
            n = names[0]
            fa = f"{' '.join(n.get('given', []))} {n.get('family', '')}".strip()
        return fa, en

    def _extract_address(self, addresses: list[dict]) -> dict[str, str]:
        if not addresses:
            return {}
        addr = addresses[0]
        return {
            "city": addr.get("city", ""),
            "state": addr.get("state", ""),
            "country": addr.get("country", ""),
            "text": addr.get("text", ""),
        }

    def _extract_code(self, code_obj: dict) -> tuple[str, str, str]:
        coding = code_obj.get("coding", [])
        if coding:
            c = coding[0]
            return c.get("code", ""), c.get("display", code_obj.get("text", "")), c.get("system", "")
        return "", code_obj.get("text", ""), ""

    def _extract_value(self, resource: dict) -> tuple[Any, str]:
        if "valueQuantity" in resource:
            vq = resource["valueQuantity"]
            return vq.get("value"), vq.get("unit", "")
        if "valueString" in resource:
            return resource["valueString"], ""
        if "valueCodeableConcept" in resource:
            _, display, _ = self._extract_code(resource["valueCodeableConcept"])
            return display, ""
        if "component" in resource:
            components = {}
            for comp in resource["component"]:
                c, d, _ = self._extract_code(comp.get("code", {}))
                val, u = self._extract_value(comp)
                components[c or d] = val
            return components, ""
        return None, ""

    def _extract_category(self, categories: list[dict]) -> str:
        for cat in categories:
            for coding in cat.get("coding", []):
                if coding.get("code"):
                    return coding["code"]
        return ""

    def _extract_interpretation(self, resource: dict) -> str:
        interp = resource.get("interpretation", [])
        if interp:
            codings = interp[0].get("coding", [])
            if codings:
                return codings[0].get("code", "")
        return ""

    def _extract_severity(self, resource: dict) -> str:
        sev = resource.get("severity", {})
        codings = sev.get("coding", [])
        return codings[0].get("code", "") if codings else ""

    def _extract_patient_id(self, resource: dict[str, Any]) -> str:
        subject = resource.get("subject", {})
        ref = subject.get("reference", "")
        if ref.startswith("Patient/"):
            return ref.split("/", 1)[1]
        return ""

    def _extract_encounter_id(self, resource: dict[str, Any]) -> str:
        enc = resource.get("encounter", {})
        ref = enc.get("reference", "")
        if ref.startswith("Encounter/"):
            return ref.split("/", 1)[1]
        return ""
