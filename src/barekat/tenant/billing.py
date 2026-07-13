"""Billing, quota enforcement, and usage metering."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import text

from barekat.storage.database import engine
from barekat.tenant.repository import get_plan

METRIC_PATIENTS = "patients"
METRIC_ADMISSIONS = "admissions"
METRIC_API_CALLS = "api_calls"
METRIC_STORAGE_GB = "storage_gb"
METRIC_ML_JOBS = "ml_jobs"

PLAN_METRIC_MAP = {
    METRIC_PATIENTS: "quota_patients",
    METRIC_ADMISSIONS: "quota_admissions",
    METRIC_API_CALLS: "quota_api_calls",
    METRIC_STORAGE_GB: "quota_storage_gb",
    METRIC_ML_JOBS: "quota_ml_jobs",
}


def record_usage(tenant_id: str, metric: str, quantity: int = 1, metadata: dict | None = None) -> None:
    query = text("""
        INSERT INTO tenant.usage_records (tenant_id, metric, quantity, metadata)
        VALUES (:tenant_id, :metric, :quantity, CAST(:metadata AS JSONB))
    """)
    period = date.today().replace(day=1)
    summary_q = text("""
        INSERT INTO tenant.usage_summary (tenant_id, period_month, metric, total_quantity)
        VALUES (:tenant_id, :period, :metric, :quantity)
        ON CONFLICT (tenant_id, period_month, metric)
        DO UPDATE SET total_quantity = tenant.usage_summary.total_quantity + EXCLUDED.total_quantity
    """)
    with engine.begin() as conn:
        conn.execute(query, {
            "tenant_id": tenant_id,
            "metric": metric,
            "quantity": quantity,
            "metadata": json.dumps(metadata or {}),
        })
        conn.execute(summary_q, {
            "tenant_id": tenant_id,
            "period": period,
            "metric": metric,
            "quantity": quantity,
        })


def get_usage_summary(tenant_id: str, period: date | None = None) -> dict[str, int]:
    period = period or date.today().replace(day=1)
    query = text("""
        SELECT metric, total_quantity FROM tenant.usage_summary
        WHERE tenant_id = :tenant_id AND period_month = :period
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"tenant_id": tenant_id, "period": period}).fetchall()
    return {r[0]: int(r[1]) for r in rows}


def get_live_counts(tenant_id: str) -> dict[str, int]:
    """Current row counts for quota comparison."""
    counts = {}
    tables = {
        METRIC_PATIENTS: "raw.patients",
        METRIC_ADMISSIONS: "raw.admissions",
    }
    with engine.connect() as conn:
        for metric, table in tables.items():
            try:
                counts[metric] = conn.execute(
                    text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id = :tid"),
                    {"tid": tenant_id},
                ).scalar() or 0
            except Exception:
                counts[metric] = 0
        counts[METRIC_API_CALLS] = get_usage_summary(tenant_id).get(METRIC_API_CALLS, 0)
    return counts


def get_quota_status(tenant_id: str, plan_id: str) -> dict[str, Any]:
    plan = get_plan(plan_id)
    if not plan:
        return {"error": "plan not found"}

    usage = get_live_counts(tenant_id)
    quotas = {}
    for metric, quota_col in PLAN_METRIC_MAP.items():
        limit = int(plan.get(quota_col, 0))
        used = usage.get(metric, 0)
        quotas[metric] = {
            "used": used,
            "limit": limit,
            "remaining": max(0, limit - used),
            "pct": round(used / limit * 100, 1) if limit > 0 else 0,
            "exceeded": used >= limit if limit > 0 else False,
        }

    any_exceeded = any(q["exceeded"] for q in quotas.values())
    return {
        "tenant_id": tenant_id,
        "plan_id": plan_id,
        "plan_name_fa": plan.get("name_fa"),
        "price_monthly_usd": float(plan.get("price_monthly_usd", 0)),
        "features": plan.get("features") or {},
        "quotas": quotas,
        "any_exceeded": any_exceeded,
        "billing_period": date.today().replace(day=1).isoformat(),
    }


def check_quota(tenant_id: str, plan_id: str, metric: str, increment: int = 1) -> tuple[bool, str]:
    status = get_quota_status(tenant_id, plan_id)
    q = status.get("quotas", {}).get(metric)
    if not q:
        return True, "ok"
    if q["remaining"] < increment:
        return False, f"Quota exceeded for {metric}: {q['used']}/{q['limit']}"
    return True, "ok"


def estimate_monthly_bill(tenant_id: str, plan_id: str) -> dict[str, Any]:
    plan = get_plan(plan_id)
    if not plan:
        return {}
    base = float(plan.get("price_monthly_usd", 0))
    usage = get_usage_summary(tenant_id)
    overage = 0.0
    # Simple overage: $0.01 per 1000 extra API calls
    api_used = usage.get(METRIC_API_CALLS, 0)
    api_limit = int(plan.get("quota_api_calls", 0))
    if api_used > api_limit:
        overage += (api_used - api_limit) / 1000 * 10.0

    return {
        "tenant_id": tenant_id,
        "plan_id": plan_id,
        "base_monthly_usd": base,
        "overage_usd": round(overage, 2),
        "estimated_total_usd": round(base + overage, 2),
        "period": date.today().replace(day=1).isoformat(),
    }
