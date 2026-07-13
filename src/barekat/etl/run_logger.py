"""ETL run logging to audit.etl_runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from barekat.storage.database import engine


def start_run(
    mode: str = "incremental",
    pipeline_name: str = "health_etl",
    celery_task_id: str | None = None,
    retry_count: int = 0,
) -> int:
    query = text("""
        INSERT INTO audit.etl_runs (pipeline_name, status, mode, celery_task_id, retry_count)
        VALUES (:pipeline_name, 'running', :mode, :celery_task_id, :retry_count)
        RETURNING run_id
    """)
    with engine.begin() as conn:
        run_id = conn.execute(query, {
            "pipeline_name": pipeline_name,
            "mode": mode,
            "celery_task_id": celery_task_id,
            "retry_count": retry_count,
        }).scalar()
    return int(run_id)


def finish_run(
    run_id: int,
    status: str,
    records_loaded: dict[str, int] | None = None,
    validation_result: dict | None = None,
    quality_checks: dict | None = None,
    error_message: str | None = None,
) -> None:
    finished_at = datetime.now(timezone.utc)
    query = text("""
        UPDATE audit.etl_runs
        SET status = :status,
            finished_at = :finished_at,
            records_loaded = CAST(:records_loaded AS JSONB),
            validation_result = CAST(:validation_result AS JSONB),
            quality_checks = CAST(:quality_checks AS JSONB),
            error_message = :error_message
        WHERE run_id = :run_id
    """)
    with engine.begin() as conn:
        conn.execute(query, {
            "run_id": run_id,
            "status": status,
            "finished_at": finished_at,
            "records_loaded": json.dumps(records_loaded or {}),
            "validation_result": json.dumps(validation_result or {}),
            "quality_checks": json.dumps(quality_checks or {}),
            "error_message": error_message,
        })
        meta = conn.execute(
            text("SELECT mode, started_at FROM audit.etl_runs WHERE run_id = :run_id"),
            {"run_id": run_id},
        ).mappings().first()

    try:
        from barekat.observability.metrics import ETL_LAST_SUCCESS, record_etl_run
        mode = (meta or {}).get("mode", "incremental")
        started = (meta or {}).get("started_at")
        duration = (finished_at - started).total_seconds() if started else None
        record_etl_run(mode, status, duration)
        if status == "success":
            ETL_LAST_SUCCESS.labels(mode=mode).set(finished_at.timestamp())
    except Exception:
        pass


def mark_retrying(run_id: int, retry_count: int, error_message: str) -> None:
    query = text("""
        UPDATE audit.etl_runs
        SET status = 'retrying', retry_count = :retry_count, error_message = :error_message
        WHERE run_id = :run_id
    """)
    with engine.begin() as conn:
        conn.execute(query, {
            "run_id": run_id,
            "retry_count": retry_count,
            "error_message": error_message,
        })


def get_recent_runs(limit: int = 20) -> list[dict[str, Any]]:
    query = text("""
        SELECT run_id, pipeline_name, status, mode, started_at, finished_at,
               records_loaded, validation_result, quality_checks, error_message, retry_count
        FROM audit.etl_runs
        ORDER BY started_at DESC
        LIMIT :limit
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"limit": limit}).mappings().all()
    return [dict(row) for row in rows]
