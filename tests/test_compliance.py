"""Tests for compliance frameworks."""

from barekat.privacy.compliance import compliance_summary, get_requirements


def test_compliance_summary_has_requirements():
    summary = compliance_summary("all")
    assert summary["total_count"] > 0
    assert "audit_trail" in {r["id"] for r in summary["requirements"]}


def test_hipaa_requirements():
    reqs = get_requirements("hipaa")
    ids = {r["id"] for r in reqs}
    assert "audit_trail" in ids
    assert "min_necessary" in ids


def test_gdpr_requirements():
    reqs = get_requirements("gdpr")
    ids = {r["id"] for r in reqs}
    assert "erasure" in ids
    assert "consent" in ids


def test_iran_requirements():
    reqs = get_requirements("iran")
    ids = {r["id"] for r in reqs}
    assert "national_id" in ids
    assert "sepas" in ids
