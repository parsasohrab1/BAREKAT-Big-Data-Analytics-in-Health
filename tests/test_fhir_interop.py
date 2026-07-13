"""Tests for FHIR R4 parser — Patient, Encounter, Observation, Condition."""

from barekat.interop.fhir.parser import FHIRParser


def test_fhir_condition_parse():
    parser = FHIRParser()
    resource = {
        "resourceType": "Condition",
        "id": "cond-1",
        "subject": {"reference": "Patient/patient-123"},
        "encounter": {"reference": "Encounter/enc-456"},
        "clinicalStatus": {"coding": [{"code": "active"}]},
        "code": {
            "coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": "A41.9", "display": "Sepsis"}],
        },
        "severity": {"coding": [{"code": "severe"}]},
    }
    events = parser.parse(resource)
    assert len(events) == 1
    assert events[0]["event_type"] == "fhir.condition"
    assert events[0]["payload"]["icd_code"] == "A41.9"


def test_fhir_patient_iranian_identifier():
    parser = FHIRParser()
    resource = {
        "resourceType": "Patient",
        "id": "ir-patient-1",
        "identifier": [{
            "system": "http://fhir.salamat.org.ir/sid/national-id",
            "value": "0012345678",
        }],
        "name": [{"family": "احمدی", "given": ["علی"], "use": "official"}],
        "gender": "male",
        "birthDate": "1985-03-15",
    }
    events = parser.parse(resource, profile_key="iran_salamat")
    assert events[0]["payload"]["national_id"] == "0012345678"
    assert events[0]["profile"] == "iran_salamat"


def test_fhir_bundle_all_resources():
    parser = FHIRParser()
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p1", "gender": "female"}},
            {"resource": {"resourceType": "Encounter", "id": "e1", "subject": {"reference": "Patient/p1"}, "status": "finished"}},
            {"resource": {
                "resourceType": "Observation", "id": "o1",
                "subject": {"reference": "Patient/p1"},
                "code": {"coding": [{"code": "8867-4"}]},
                "valueQuantity": {"value": 88, "unit": "bpm"},
            }},
            {"resource": {
                "resourceType": "Condition", "id": "c1",
                "subject": {"reference": "Patient/p1"},
                "code": {"coding": [{"code": "I10", "display": "Hypertension"}]},
                "clinicalStatus": {"coding": [{"code": "active"}]},
            }},
        ],
    }
    events = parser.parse(bundle)
    types = {e["resource_type"] for e in events}
    assert types == {"Patient", "Encounter", "Observation", "Condition"}
