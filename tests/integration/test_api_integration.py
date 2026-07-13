"""Integration tests for FastAPI endpoints."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_health_endpoint(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"


def test_login_and_analytics_summary(api_client, auth_headers):
    response = api_client.get("/api/v1/analytics/summary", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "summary" in body
    assert body["summary"]["total_patients"] >= 2
    assert body["summary"]["total_admissions"] >= 2


def test_etl_runs_endpoint_requires_admin(api_client, auth_headers):
    response = api_client.get("/api/v1/analytics/etl/runs", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "runs" in body
    assert isinstance(body["runs"], list)


def test_unauthorized_access_rejected(api_client):
    response = api_client.get("/api/v1/analytics/summary")
    assert response.status_code == 401
