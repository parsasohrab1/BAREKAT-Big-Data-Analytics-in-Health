"""Integration tests for DB auth and tenant resolution."""

import pytest


@pytest.mark.integration
def test_login_uses_database_users(api_client):
    response = api_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body.get("role") == "admin"


@pytest.mark.integration
def test_clinician_tenant_from_database(api_client):
    response = api_client.post(
        "/api/v1/auth/login",
        json={"username": "clinician", "password": "clinician123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    from jose import jwt
    from barekat.config.settings import get_settings

    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    assert payload.get("tenant_id") == "tehran-general"


@pytest.mark.integration
def test_invalid_password_rejected(api_client):
    response = api_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert response.status_code == 401
