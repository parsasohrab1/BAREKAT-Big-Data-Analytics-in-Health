"""Sync DB state into Prometheus gauges (ETL, alerts, lake jobs)."""

from __future__ import annotations

import structlog
from sqlalchemy import text

from barekat.observability.metrics import (
    ACTIVE_ALERTS,
    ETL_LAST_SUCCESS,
    LAKE_JOB_STATUS,
    record_ml_metrics,
)
from barekat.storage.database import engine

logger = structlog.get_logger(__name__)


def refresh_metrics_from_db() -> None:
    """Poll PostgreSQL and update Prometheus gauges."""
    _refresh_etl_timestamps()
    _refresh_alert_counts()
    _refresh_ml_models()
    _refresh_lake_jobs()


def _refresh_etl_timestamps() -> None:
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT mode, MAX(EXTRACT(EPOCH FROM finished_at)) AS ts
                FROM audit.etl_runs
                WHERE status = 'success' AND finished_at IS NOT NULL
                GROUP BY mode
            """)).mappings().all()
        for row in rows:
            if row["ts"]:
                ETL_LAST_SUCCESS.labels(mode=row["mode"]).set(float(row["ts"]))
    except Exception as exc:
        logger.debug("etl_metrics_refresh_failed", error=str(exc))


def _refresh_alert_counts() -> None:
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT severity, COUNT(*) AS cnt
                FROM analytics.predictive_alerts
                WHERE is_acknowledged = FALSE
                GROUP BY severity
            """)).mappings().all()
        for row in rows:
            ACTIVE_ALERTS.labels(severity=row["severity"]).set(row["cnt"])
    except Exception as exc:
        logger.debug("alert_metrics_refresh_failed", error=str(exc))


def _refresh_ml_models() -> None:
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT model_name, metrics
                FROM analytics.ml_model_registry
                WHERE is_active = TRUE
            """)).mappings().all()
        for row in rows:
            metrics = row["metrics"] or {}
            if isinstance(metrics, str):
                import json
                metrics = json.loads(metrics)
            record_ml_metrics(row["model_name"], metrics)
    except Exception as exc:
        logger.debug("ml_metrics_refresh_failed", error=str(exc))


def _refresh_lake_jobs() -> None:
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT DISTINCT ON (job_name) job_name, status
                FROM lake.job_runs
                ORDER BY job_name, started_at DESC
            """)).mappings().all()
        for row in rows:
            LAKE_JOB_STATUS.labels(job_name=row["job_name"]).set(
                1 if row["status"] == "success" else 0
            )
    except Exception as exc:
        logger.debug("lake_metrics_refresh_failed", error=str(exc))
