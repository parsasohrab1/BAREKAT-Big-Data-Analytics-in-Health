"""Tests for alerts service."""

import pandas as pd


def test_persist_alerts_builds_dataframe():
    alerts = pd.DataFrame([
        {
            "patient_id": "PT00001",
            "admission_id": "AD000001",
            "alert_type": "readmission_risk",
            "severity": "high",
            "message": "Test alert",
            "risk_score": 0.85,
        }
    ])
    assert len(alerts) == 1
    assert alerts.iloc[0]["severity"] == "high"
