"""ML model versioning and registry."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
from sqlalchemy import text

from barekat.config.settings import get_settings
from barekat.storage.database import engine


def _models_root() -> Path:
    root = Path(get_settings().data_models_path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def generate_version() -> str:
    return datetime.now(timezone.utc).strftime("v%Y%m%d_%H%M%S")


def save_artifact(model_name: str, version: str, artifact: dict) -> Path:
    path = _models_root() / model_name / version / "model.joblib"
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, path)
    return path


def register_model(
    model_name: str,
    artifact: dict,
    metrics: dict,
    calibration: dict | None = None,
    samples: int = 0,
    version: str | None = None,
    set_active: bool = True,
) -> dict:
    version = version or generate_version()
    artifact_path = save_artifact(model_name, version, artifact)

    with engine.begin() as conn:
        if set_active:
            conn.execute(
                text("UPDATE analytics.ml_model_registry SET is_active = FALSE WHERE model_name = :name"),
                {"name": model_name},
            )
        conn.execute(
            text("""
                INSERT INTO analytics.ml_model_registry
                    (model_name, version, artifact_path, is_active, metrics, calibration, samples)
                VALUES
                    (:name, :version, :path, :active, CAST(:metrics AS JSONB),
                     CAST(:calibration AS JSONB), :samples)
            """),
            {
                "name": model_name,
                "version": version,
                "path": str(artifact_path),
                "active": set_active,
                "metrics": json.dumps(metrics),
                "calibration": json.dumps(calibration or metrics.get("calibration", {})),
                "samples": samples,
            },
        )

    result = {
        "model_name": model_name,
        "version": version,
        "artifact_path": str(artifact_path),
        "is_active": set_active,
        "metrics": metrics,
    }
    _post_register_hooks(model_name, metrics)
    return result


def _post_register_hooks(model_name: str, metrics: dict) -> None:
    try:
        from barekat.observability.metrics import record_ml_metrics
        from barekat.observability.drift import check_model_drift
        record_ml_metrics(model_name, metrics)
        check_model_drift(model_name)
    except Exception:
        pass


def load_active_artifact(model_name: str) -> dict | None:
    query = text("""
        SELECT artifact_path FROM analytics.ml_model_registry
        WHERE model_name = :name AND is_active = TRUE
        ORDER BY trained_at DESC LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"name": model_name}).mappings().first()

    if row and Path(row["artifact_path"]).exists():
        return joblib.load(row["artifact_path"])

    # Fallback to legacy flat paths
    legacy_map = {
        "readmission": "readmission_model.joblib",
        "clustering": "clustering_model.joblib",
    }
    if model_name in legacy_map:
        legacy = _models_root() / legacy_map[model_name]
        if legacy.exists():
            return joblib.load(legacy)
    return None


def list_models(model_name: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    if model_name:
        query = text("""
            SELECT model_id, model_name, version, is_active, metrics, calibration, samples, trained_at
            FROM analytics.ml_model_registry
            WHERE model_name = :name
            ORDER BY trained_at DESC LIMIT :limit
        """)
        params = {"name": model_name, "limit": limit}
    else:
        query = text("""
            SELECT model_id, model_name, version, is_active, metrics, calibration, samples, trained_at
            FROM analytics.ml_model_registry
            ORDER BY trained_at DESC LIMIT :limit
        """)
        params = {"limit": limit}

    with engine.connect() as conn:
        rows = conn.execute(query, params).mappings().all()
    return [dict(row) for row in rows]


def get_active_model(model_name: str) -> dict | None:
    query = text("""
        SELECT model_id, model_name, version, artifact_path, metrics, calibration, samples, trained_at
        FROM analytics.ml_model_registry
        WHERE model_name = :name AND is_active = TRUE
        ORDER BY trained_at DESC LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"name": model_name}).mappings().first()
    return dict(row) if row else None
