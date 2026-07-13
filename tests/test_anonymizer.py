"""Tests for anonymization and de-identification."""

from barekat.privacy.anonymizer import deidentify_for_export, _pseudonym_for


def test_pseudonym_is_deterministic():
    a = _pseudonym_for("PT00001")
    b = _pseudonym_for("PT00001")
    assert a == b
    assert a.startswith("PSN-")


def test_deidentify_removes_phi_fields():
    records = [{
        "patient_id": "PT00001",
        "patient_name": "Ali Rezaei",
        "age": 45,
        "national_id": "1234567890",
        "gender": "M",
    }]
    result = deidentify_for_export(records)
    assert "patient_name" not in result[0]
    assert "national_id" not in result[0]
    assert result[0]["patient_id"].startswith("PSN-")
    assert result[0]["age"] == 40  # generalized to decade
