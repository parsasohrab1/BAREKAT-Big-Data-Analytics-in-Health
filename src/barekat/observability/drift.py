"""Model drift detection — PSI and AUC degradation."""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog
from sqlalchemy import text

from barekat.config.settings import get_settings
from barekat.observability.metrics import record_drift
from barekat.storage.database import engine

logger = structlog.get_logger(__name__)


def compute_psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index between two distributions."""
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    if len(expected) < bins or len(actual) < bins:
        return 0.0

    breakpoints = np.percentile(expected, np.linspace(0, 100, bins + 1))
    breakpoints = np.unique(breakpoints)
    if len(breakpoints) < 2:
        return 0.0

    expected_perc = np.histogram(expected, bins=breakpoints)[0] / max(len(expected), 1)
    actual_perc = np.histogram(actual, bins=breakpoints)[0] / max(len(actual), 1)

    expected_perc = np.clip(expected_perc, 1e-6, None)
    actual_perc = np.clip(actual_perc, 1e-6, None)
    psi = float(np.sum((actual_perc - expected_perc) * np.log(actual_perc / expected_perc)))
    return round(psi, 4)


def check_model_drift(model_name: str = "readmission") -> dict[str, Any]:
    """Compare active model metrics vs baseline and score distribution PSI."""
    settings = get_settings()
    baseline_auc = _get_baseline_auc(model_name)
    current = _get_active_metrics(model_name)

    current_auc = float(current.get("auc") or 0)
    auc_drop = round(max(0.0, baseline_auc - current_auc), 4) if baseline_auc else 0.0

    psi = _estimate_feature_psi(model_name)

    drift_detected = (
        auc_drop >= settings.drift_auc_drop_threshold
        or psi >= settings.drift_psi_threshold
    )

    record_drift(model_name, psi, auc_drop, drift_detected)

    result = {
        "model_name": model_name,
        "baseline_auc": baseline_auc,
        "current_auc": current_auc,
        "auc_drop": auc_drop,
        "psi": psi,
        "drift_detected": drift_detected,
        "thresholds": {
            "auc_drop": settings.drift_auc_drop_threshold,
            "psi": settings.drift_psi_threshold,
        },
    }

    if drift_detected:
        logger.warning("model_drift_detected", **result)
        _persist_drift_event(result)

    return result


def check_all_models() -> list[dict[str, Any]]:
    models = ["readmission", "los", "early_warning", "vitals"]
    return [check_model_drift(m) for m in models if _get_active_metrics(m)]


def _get_baseline_auc(model_name: str) -> float:
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT metrics->>'auc' AS auc FROM analytics.ml_model_registry
                WHERE model_name = :name
                ORDER BY trained_at ASC LIMIT 1
            """),
            {"name": model_name},
        ).mappings().first()
    if row and row["auc"]:
        return float(row["auc"])
    return 0.0


def _get_active_metrics(model_name: str) -> dict[str, Any]:
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT metrics FROM analytics.ml_model_registry
                WHERE model_name = :name AND is_active = TRUE
                ORDER BY trained_at DESC LIMIT 1
            """),
            {"name": model_name},
        ).mappings().first()
    if not row:
        return {}
    metrics = row["metrics"]
    if isinstance(metrics, str):
        import json
        return json.loads(metrics)
    return dict(metrics) if metrics else {}


def _estimate_feature_psi(model_name: str) -> float:
    """PSI on readmission risk scores: training baseline vs recent admissions."""
    try:
        with engine.connect() as conn:
            baseline = conn.execute(text("""
                SELECT risk_score::float FROM analytics.predictive_alerts
                WHERE alert_type LIKE :pattern
                ORDER BY created_at ASC LIMIT 500
            """), {"pattern": f"%{model_name}%"}).scalars().all()

            recent = conn.execute(text("""
                SELECT risk_score::float FROM analytics.predictive_alerts
                WHERE alert_type LIKE :pattern
                ORDER BY created_at DESC LIMIT 500
            """), {"pattern": f"%{model_name}%"}).scalars().all()

        if len(baseline) >= 20 and len(recent) >= 20:
            return compute_psi(np.array(baseline), np.array(recent))
    except Exception:
        pass
    return 0.0


def _persist_drift_event(result: dict[str, Any]) -> None:
    try:
        import json
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO observability.drift_events
                        (model_name, auc_drop, psi, drift_detected, details)
                    VALUES (:model_name, :auc_drop, :psi, :drift_detected, :details::jsonb)
                """),
                {
                    "model_name": result["model_name"],
                    "auc_drop": result["auc_drop"],
                    "psi": result["psi"],
                    "drift_detected": result["drift_detected"],
                    "details": json.dumps(result),
                },
            )
    except Exception as exc:
        logger.warning("drift_persist_failed", error=str(exc))
