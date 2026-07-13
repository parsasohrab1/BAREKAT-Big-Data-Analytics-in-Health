"""Tests for FHIR profile registry."""

from barekat.interop.fhir.profiles import list_profiles


def test_iranian_profiles_exist():
    profiles = list_profiles(region="IR")
    keys = {p["key"] for p in profiles}
    assert "iran_moh" in keys
    assert "iran_salamat" in keys
    assert "iran_tamin" in keys


def test_international_profiles_exist():
    profiles = list_profiles(region="INT")
    keys = {p["key"] for p in profiles}
    assert "international_hapi" in keys
    assert "international_epic" in keys
    assert "international_us_core" in keys
