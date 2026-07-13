"""Tests for secrets loader."""

from pathlib import Path

from barekat.config.secrets import read_secret


def test_read_secret_from_file(tmp_path, monkeypatch):
    secret_file = tmp_path / "jwt_secret"
    secret_file.write_text("my-super-secret\n")
    monkeypatch.setenv("JWT_SECRET_FILE", str(secret_file))
    assert read_secret("jwt_secret", env_fallback="JWT_SECRET") == "my-super-secret"


def test_read_secret_env_fallback(monkeypatch):
    monkeypatch.delenv("JWT_SECRET_FILE", raising=False)
    monkeypatch.setenv("JWT_SECRET", "from-env")
    from barekat.config import secrets as secrets_mod
    secrets_mod.get_jwt_secret.cache_clear()
    assert read_secret("jwt_secret", env_fallback="JWT_SECRET") == "from-env"
