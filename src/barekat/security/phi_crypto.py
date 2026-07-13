"""PHI field encryption at rest (application-level Fernet)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from barekat.config.secrets import get_phi_encryption_key
from barekat.config.settings import get_settings

ENC_PREFIX = "enc:v1:"


def _fernet() -> Fernet | None:
    settings = get_settings()
    if not settings.phi_encryption_enabled:
        return None
    key_material = get_phi_encryption_key()
    if not key_material:
        return None
    # Derive valid 32-byte Fernet key from secret
    digest = hashlib.sha256(key_material.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def encrypt_phi(plaintext: str) -> str:
    """Encrypt PHI text for database storage."""
    f = _fernet()
    if f is None or not plaintext:
        return plaintext
    if plaintext.startswith(ENC_PREFIX):
        return plaintext
    token = f.encrypt(plaintext.encode("utf-8")).decode("ascii")
    return f"{ENC_PREFIX}{token}"


def decrypt_phi(ciphertext: str) -> str:
    """Decrypt PHI text from database."""
    if not ciphertext or not ciphertext.startswith(ENC_PREFIX):
        return ciphertext
    f = _fernet()
    if f is None:
        return "[ENCRYPTED — key unavailable]"
    token = ciphertext[len(ENC_PREFIX):]
    try:
        return f.decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return "[ENCRYPTED — decryption failed]"


def is_encrypted(value: str) -> bool:
    return bool(value and value.startswith(ENC_PREFIX))


def phi_encryption_active() -> bool:
    settings = get_settings()
    return settings.phi_encryption_enabled and get_phi_encryption_key() is not None
