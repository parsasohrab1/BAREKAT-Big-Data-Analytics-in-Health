"""Tests for multi-tenancy."""

from barekat.tenant.context import TenantContext, get_tenant_id, set_current_tenant
from barekat.tenant.isolation import tenant_filter, tenant_params


def test_tenant_context():
    ctx = TenantContext(tenant_id="tehran-general", slug="tehran-general", name_fa="تهران")
    set_current_tenant(ctx)
    assert get_tenant_id() == "tehran-general"
    set_current_tenant(None)
    assert get_tenant_id() == "default"


def test_tenant_sql_helpers():
    assert tenant_filter() == "tenant_id = :tenant_id"
    assert tenant_filter("a") == "a = :tenant_id"
    params = tenant_params("isfahan-medical")
    assert params["tenant_id"] == "isfahan-medical"


def test_quota_status_structure():
    from barekat.tenant.billing import get_quota_status

    # Uses DB if available; validate structure with mock plan
    from barekat.tenant.billing import PLAN_METRIC_MAP
    assert "patients" in PLAN_METRIC_MAP
    assert "api_calls" in PLAN_METRIC_MAP
