"""Tests for weekly reports and notifications."""

from unittest.mock import MagicMock, patch

from barekat.services.notifications import (
    SEVERITY_RANK,
    _mask_recipient,
    _meets_threshold,
    dispatch_critical_alert,
)
from barekat.services.reports import (
    generate_excel_report,
    generate_pdf_report,
    generate_weekly_html,
)


def test_severity_threshold():
    assert _meets_threshold("critical", "critical")
    assert _meets_threshold("high", "critical") is False
    assert _meets_threshold("critical", "high")


def test_mask_recipient():
    assert "@" in _mask_recipient("admin@hospital.ir")
    assert _mask_recipient("09121234567").endswith("***")


def test_generate_weekly_html():
    metrics = {
        "tenant_name": "تست",
        "period_start": "2026-07-06",
        "period_end": "2026-07-12",
        "admissions_total": 10,
        "readmission_rate_pct": 5.2,
        "alerts_critical": 1,
        "alerts_by_severity": {"critical": 1, "high": 2},
        "top_departments": [{"department": "Cardiology", "cnt": 5}],
    }
    html = generate_weekly_html(metrics)
    assert "گزارش هفتگی" in html
    assert "Cardiology" in html


def test_excel_and_pdf_generation():
    metrics = {
        "tenant_id": "default",
        "tenant_name": "Default",
        "period_start": "2026-07-06",
        "period_end": "2026-07-12",
        "admissions_total": 5,
        "avg_length_of_stay": 4.2,
        "readmission_rate_pct": 3.1,
        "unique_patients": 4,
        "alerts_critical": 0,
        "alerts_high": 1,
        "alerts_by_severity": {"high": 1},
        "top_departments": [],
    }
    excel = generate_excel_report(metrics)
    pdf = generate_pdf_report(metrics)
    assert excel[:2] == b"PK"
    assert pdf[:4] == b"%PDF"


@patch("barekat.services.notifications.get_notification_recipients")
@patch("barekat.services.notifications.send_email")
@patch("barekat.services.notifications.send_sms")
@patch("barekat.services.notifications.get_settings")
def test_dispatch_critical_alert(mock_settings, mock_sms, mock_email, mock_recipients):
    mock_settings.return_value = MagicMock(
        notifications_enabled=True,
        alert_notify_min_severity="critical",
    )
    mock_recipients.return_value = [{
        "user_email": "mgr@test.ir",
        "phone": "09120000000",
        "email_enabled": True,
        "sms_enabled": True,
        "alert_min_severity": "critical",
    }]
    mock_email.return_value = True
    mock_sms.return_value = True

    alert = {
        "severity": "critical",
        "alert_type": "sepsis_risk",
        "patient_id": "PT001",
        "admission_id": "AD001",
        "message": "Test critical",
        "risk_score": 0.92,
    }
    sent = dispatch_critical_alert(alert, tenant_id="default")
    assert sent["email"] == 1
    assert sent["sms"] == 1


def test_severity_rank_order():
    assert SEVERITY_RANK["critical"] > SEVERITY_RANK["high"]
