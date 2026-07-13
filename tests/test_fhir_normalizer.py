"""Tests for FHIR → raw schema mapping."""

from barekat.interop.fhir.normalizer import map_to_raw_records


def test_map_condition_to_diagnosis():
    events = [{
        "resource_type": "Condition",
        "resource_id": "c1",
        "patient_id": "p1",
        "admission_id": "e1",
        "payload": {
            "icd_code": "I10",
            "diagnosis_description": "Hypertension",
            "clinical_status": "active",
        },
    }]
    records = map_to_raw_records(events)
    assert len(records["diagnoses"]) == 1
    assert records["diagnoses"][0]["icd_code"] == "I10"
