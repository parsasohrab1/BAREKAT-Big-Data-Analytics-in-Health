"""Tests for PHI encryption at rest."""

import os

import pytest

from barekat.security.phi_crypto import decrypt_phi, encrypt_phi, is_encrypted


@pytest.fixture(autouse=True)
def enable_phi_encryption(monkeypatch):
    monkeypatch.setenv("PHI_ENCRYPTION_ENABLED", "true")
    monkeypatch.setenv("PHI_ENCRYPTION_KEY", "test-phi-key-for-unit-tests-only")
    # Clear cached secrets
    from barekat.config import secrets as secrets_mod
    from barekat.config import settings as settings_mod
    secrets_mod.get_phi_encryption_key.cache_clear()
    settings_mod.get_settings.cache_clear()
    yield
    secrets_mod.get_phi_encryption_key.cache_clear()
    settings_mod.get_settings.cache_clear()


def test_encrypt_decrypt_roundtrip():
    plain = "Patient complains of chest pain and shortness of breath."
    enc = encrypt_phi(plain)
    assert is_encrypted(enc)
    assert decrypt_phi(enc) == plain


def test_plaintext_passthrough_when_disabled(monkeypatch):
    monkeypatch.setenv("PHI_ENCRYPTION_ENABLED", "false")
    from barekat.config.settings import get_settings
    get_settings.cache_clear()
    text = "not encrypted"
    assert encrypt_phi(text) == text
