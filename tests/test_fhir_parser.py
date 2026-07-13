"""Tests for FHIR parser."""

from barekat.ingestion.fhir_parser import FHIRParser


def test_fhir_observation_parse():
    parser = FHIRParser()
    resource = {
        "resourceType": "Observation",
        "id": "obs-1",
        "subject": {"reference": "Patient/patient-123"},
        "code": {"coding": [{"code": "8867-4", "display": "Heart rate"}]},
        "valueQuantity": {"value": 110, "unit": "beats/min"},
    }
    assert parser.validate(resource)
    events = parser.parse(resource)
    assert len(events) == 1
    assert events[0]["patient_id"] == "patient-123"
    assert events[0]["payload"]["vital_key"] == "heart_rate"
