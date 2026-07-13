"""Tests for streaming alert processors."""

from barekat.streaming.processors import detect_alerts


def test_vital_alert_high_heart_rate():
    event = {
        "event_id": "e1",
        "source": "hl7",
        "event_type": "hl7.lab_result",
        "patient_id": "PT00001",
        "admission_id": "AD000001",
        "payload": {"vitals": [{"key": "heart_rate", "value": 145}]},
    }
    alerts = detect_alerts(event)
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "critical"
    assert alerts[0]["alert_type"] == "vitals_deterioration"


def test_vital_alert_normal_no_alert():
    event = {
        "event_id": "e2",
        "source": "fhir",
        "event_type": "fhir.observation",
        "patient_id": "PT00002",
        "payload": {"vital_key": "heart_rate", "value": 78},
    }
    alerts = detect_alerts(event)
    assert alerts == []


def test_condition_alert_sepsis():
    event = {
        "event_id": "e3",
        "source": "fhir",
        "event_type": "fhir.condition",
        "patient_id": "PT00003",
        "admission_id": "AD000003",
        "payload": {
            "icd_code": "A41.9",
            "diagnosis_description": "Sepsis",
            "clinical_status": "active",
        },
    }
    alerts = detect_alerts(event)
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "condition_alert"
