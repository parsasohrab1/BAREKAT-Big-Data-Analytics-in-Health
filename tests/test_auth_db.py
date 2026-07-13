"""Tests for database-backed authentication."""

import pytest

from barekat.security.auth import authenticate_user, hash_password, verify_password


def test_verify_password_bcrypt():
    hashed = hash_password("admin123")
    assert verify_password("admin123", hashed)
    assert not verify_password("wrong", hashed)


def test_authenticate_rejects_dev_fallback_when_disabled(monkeypatch):
    from barekat.config.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AUTH_USE_DATABASE", "false")
    monkeypatch.setenv("AUTH_DEV_FALLBACK", "false")
    monkeypatch.setenv("BAREKAT_ENV", "production")
    get_settings.cache_clear()

    assert authenticate_user("admin", "admin123") is None
    get_settings.cache_clear()


def test_authenticate_dev_fallback_in_development(monkeypatch):
    from barekat.config.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AUTH_USE_DATABASE", "false")
    monkeypatch.setenv("AUTH_DEV_FALLBACK", "true")
    monkeypatch.setenv("BAREKAT_ENV", "development")
    get_settings.cache_clear()

    user = authenticate_user("clinician", "clinician123")
    assert user is not None
    assert user["role"] == "clinician"
    get_settings.cache_clear()
