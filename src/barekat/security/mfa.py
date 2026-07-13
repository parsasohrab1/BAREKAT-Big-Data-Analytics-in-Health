"""TOTP MFA for admin users."""

from __future__ import annotations

import base64
import io
from typing import Any

import pyotp
import qrcode
from sqlalchemy import text

from barekat.security.phi_crypto import decrypt_phi, encrypt_phi
from barekat.storage.database import engine

MFA_ISSUER = "BAREKAT Health"


def get_mfa_status(username: str) -> dict[str, Any]:
    query = text("""
        SELECT mfa_enabled, enrolled_at FROM audit.user_mfa WHERE username = :username
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"username": username}).mappings().first()
    if not row:
        return {"enabled": False, "enrolled": False}
    return {"enabled": row["mfa_enabled"], "enrolled": True, "enrolled_at": row["enrolled_at"]}


def is_mfa_required(username: str, role: str) -> bool:
    from barekat.config.settings import get_settings

    settings = get_settings()
    if not settings.mfa_required_for_admin or role != "admin":
        return False
    return get_mfa_status(username).get("enabled", False)


def enroll_mfa(username: str) -> dict[str, Any]:
    secret = pyotp.random_base32()
    encrypted = encrypt_phi(secret)
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=username, issuer_name=MFA_ISSUER)

    query = text("""
        INSERT INTO audit.user_mfa (username, totp_secret, mfa_enabled, enrolled_at)
        VALUES (:username, :secret, FALSE, NOW())
        ON CONFLICT (username) DO UPDATE
        SET totp_secret = EXCLUDED.totp_secret, mfa_enabled = FALSE, enrolled_at = NOW()
    """)
    with engine.begin() as conn:
        conn.execute(query, {"username": username, "secret": encrypted})

    return {
        "secret": secret,
        "provisioning_uri": uri,
        "qr_code_base64": _qr_base64(uri),
        "message": "Scan QR with authenticator app, then POST /auth/mfa/verify to activate",
    }


def activate_mfa(username: str, code: str) -> bool:
    secret = _load_secret(username, require_enabled=False)
    if not secret or not pyotp.TOTP(secret).verify(code, valid_window=1):
        return False

    query = text("""
        UPDATE audit.user_mfa SET mfa_enabled = TRUE, last_verified = NOW()
        WHERE username = :username
    """)
    with engine.begin() as conn:
        conn.execute(query, {"username": username})
    return True


def verify_mfa_code(username: str, code: str) -> bool:
    secret = _load_secret(username, require_enabled=True)
    if not secret:
        return False
    valid = pyotp.TOTP(secret).verify(code, valid_window=1)
    if valid:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE audit.user_mfa SET last_verified = NOW() WHERE username = :username
            """), {"username": username})
    return valid


def _load_secret(username: str, *, require_enabled: bool) -> str | None:
    enabled_clause = "AND mfa_enabled = TRUE" if require_enabled else ""
    query = text(f"""
        SELECT totp_secret FROM audit.user_mfa
        WHERE username = :username {enabled_clause}
    """)
    with engine.connect() as conn:
        encrypted = conn.execute(query, {"username": username}).scalar()
    if not encrypted:
        return None
    return decrypt_phi(encrypted)


def _qr_base64(uri: str) -> str:
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def create_mfa_challenge_token(username: str, role: str, email: str) -> str:
    from datetime import timedelta

    from barekat.security.auth import create_access_token

    return create_access_token(
        {"sub": username, "role": role, "email": email, "mfa_pending": True},
        expires_delta=timedelta(minutes=5),
    )
