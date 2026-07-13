"""Secret loading — Docker Secrets, file mounts, or HashiCorp Vault."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import httpx


def _read_file(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
        return value or None
    except OSError:
        return None


def read_secret(name: str, *, env_fallback: str | None = None) -> str | None:
    """
    Resolution order:
    1. {NAME}_FILE env → read file path
    2. /run/secrets/{name} (Docker Secrets)
    3. SECRETS_DIR/{name}
    4. Vault KV v2 (if VAULT_ADDR + VAULT_TOKEN set)
    5. env_fallback direct env var value
    """
    file_env = os.getenv(f"{name.upper()}_FILE")
    if file_env:
        value = _read_file(Path(file_env))
        if value:
            return value

    docker_secret = Path(f"/run/secrets/{name}")
    value = _read_file(docker_secret)
    if value:
        return value

    secrets_dir = os.getenv("SECRETS_DIR")
    if secrets_dir:
        value = _read_file(Path(secrets_dir) / name)
        if value:
            return value

    vault_value = _read_from_vault(name)
    if vault_value:
        return vault_value

    if env_fallback is not None:
        return os.getenv(env_fallback) or None

    return os.getenv(name)


def _read_from_vault(secret_name: str) -> str | None:
    vault_addr = os.getenv("VAULT_ADDR")
    if not vault_addr:
        return None

    token_file = os.getenv("VAULT_TOKEN_FILE", "/run/secrets/vault_token")
    token = _read_file(Path(token_file)) or os.getenv("VAULT_TOKEN")
    if not token:
        return None

    mount = os.getenv("VAULT_KV_MOUNT", "secret")
    path = os.getenv("VAULT_SECRET_PATH", "barekat")
    url = f"{vault_addr.rstrip('/')}/v1/{mount}/data/{path}"

    try:
        resp = httpx.get(url, headers={"X-Vault-Token": token}, timeout=5.0)
        if resp.status_code != 200:
            return None
        data = resp.json().get("data", {}).get("data", {})
        return data.get(secret_name) or data.get(secret_name.lower())
    except httpx.HTTPError:
        return None


@lru_cache
def get_jwt_secret() -> str:
    return read_secret("jwt_secret", env_fallback="JWT_SECRET") or "change-me-in-production"


@lru_cache
def get_postgres_password() -> str:
    return read_secret("postgres_password", env_fallback="POSTGRES_PASSWORD") or "barekat_secret"


@lru_cache
def get_phi_encryption_key() -> str | None:
    return read_secret("phi_encryption_key", env_fallback="PHI_ENCRYPTION_KEY")


@lru_cache
def get_pseudonymization_salt() -> str:
    return read_secret("pseudonymization_salt", env_fallback="PSEUDONYMIZATION_SALT") or "change-me-pseudonym-salt"


@lru_cache
def get_minio_secret_key() -> str:
    return read_secret("minio_secret_key", env_fallback="MINIO_SECRET_KEY") or "barekat_minio_secret"
