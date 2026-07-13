"""Tests for MFA TOTP."""

import pytest

pytest.importorskip("pyotp")

import pyotp

from barekat.security.mfa import _qr_base64


def test_qr_generation():
    uri = "otpauth://totp/BAREKAT:admin?secret=JBSWY3DPEHPK3PXP&issuer=BAREKAT"
    b64 = _qr_base64(uri)
    assert len(b64) > 100


def test_totp_verify():
    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret).now()
    assert pyotp.TOTP(secret).verify(code, valid_window=1)
