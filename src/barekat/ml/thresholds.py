"""Per-department readmission risk thresholds."""

from __future__ import annotations

from sqlalchemy import text

from barekat.config.settings import get_settings
from barekat.storage.database import engine

DEFAULT_DEPARTMENT_THRESHOLDS: dict[str, float] = {
    "Cardiology": 0.75,
    "Neurology": 0.70,
    "Oncology": 0.72,
    "Orthopedics": 0.68,
    "Internal Medicine": 0.70,
    "Pediatrics": 0.65,
    "Surgery": 0.73,
    "Psychiatry": 0.68,
}


def get_default_threshold() -> float:
    return get_settings().ml_readmission_threshold


def load_all_thresholds() -> dict[str, float]:
    thresholds = dict(DEFAULT_DEPARTMENT_THRESHOLDS)
    default = get_default_threshold()

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT department, risk_threshold FROM analytics.department_risk_thresholds"
            )).mappings().all()
        for row in rows:
            thresholds[row["department"]] = float(row["risk_threshold"])
    except Exception:
        pass

    thresholds["_default"] = default
    return thresholds


def get_threshold(department: str) -> float:
    thresholds = load_all_thresholds()
    return thresholds.get(department, thresholds.get("_default", get_default_threshold()))


def set_threshold(department: str, threshold: float) -> None:
    if not 0 <= threshold <= 1:
        raise ValueError("Threshold must be between 0 and 1")

    query = text("""
        INSERT INTO analytics.department_risk_thresholds (department, risk_threshold, updated_at)
        VALUES (:department, :threshold, NOW())
        ON CONFLICT (department) DO UPDATE SET
            risk_threshold = EXCLUDED.risk_threshold,
            updated_at = NOW()
    """)
    with engine.begin() as conn:
        conn.execute(query, {"department": department, "threshold": threshold})


def list_thresholds() -> list[dict]:
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT department, risk_threshold, updated_at FROM analytics.department_risk_thresholds ORDER BY department"
            )).mappings().all()
        return [dict(row) for row in rows]
    except Exception:
        return [
            {"department": k, "risk_threshold": v, "updated_at": None}
            for k, v in DEFAULT_DEPARTMENT_THRESHOLDS.items()
        ]
