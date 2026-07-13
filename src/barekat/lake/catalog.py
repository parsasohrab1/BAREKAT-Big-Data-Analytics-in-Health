"""Lake table catalog — versioning metadata in PostgreSQL."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from barekat.storage.database import engine


def register_table(
    layer: str,
    table_name: str,
    storage_path: str,
    *,
    fmt: str = "parquet",
    row_count: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO lake.table_registry
                    (layer, table_name, format, storage_path, row_count, last_commit_at, metadata, version)
                VALUES (:layer, :table_name, :fmt, :storage_path, :row_count, NOW(), :metadata::jsonb, 1)
                ON CONFLICT (layer, table_name) DO UPDATE SET
                    format = EXCLUDED.format,
                    storage_path = EXCLUDED.storage_path,
                    row_count = EXCLUDED.row_count,
                    last_commit_at = NOW(),
                    metadata = EXCLUDED.metadata,
                    version = lake.table_registry.version + 1,
                    updated_at = NOW()
            """),
            {
                "layer": layer,
                "table_name": table_name,
                "fmt": fmt,
                "storage_path": storage_path,
                "row_count": row_count,
                "metadata": json.dumps(metadata or {}),
            },
        )


def list_tables(layer: str | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM lake.table_registry"
    params: dict[str, Any] = {}
    if layer:
        query += " WHERE layer = :layer"
        params["layer"] = layer
    query += " ORDER BY layer, table_name"
    with engine.connect() as conn:
        rows = conn.execute(text(query), params).mappings().all()
    return [dict(r) for r in rows]


def get_table(layer: str, table_name: str) -> dict[str, Any] | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM lake.table_registry WHERE layer = :layer AND table_name = :table_name"),
            {"layer": layer, "table_name": table_name},
        ).mappings().first()
    return dict(row) if row else None


def start_job(job_name: str, layer: str | None = None) -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO lake.job_runs (job_name, layer, status)
                VALUES (:job_name, :layer, 'running') RETURNING run_id
            """),
            {"job_name": job_name, "layer": layer},
        ).scalar()
    return int(row)


def finish_job(
    run_id: int,
    *,
    status: str,
    records_processed: int | None = None,
    tables_processed: list[str] | None = None,
    error_message: str | None = None,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE lake.job_runs SET
                    status = :status,
                    records_processed = :records_processed,
                    tables_processed = :tables_processed,
                    error_message = :error_message,
                    finished_at = NOW()
                WHERE run_id = :run_id
            """),
            {
                "run_id": run_id,
                "status": status,
                "records_processed": records_processed,
                "tables_processed": tables_processed,
                "error_message": error_message,
            },
        )


def recent_jobs(limit: int = 20) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM lake.job_runs ORDER BY started_at DESC LIMIT :limit"),
            {"limit": limit},
        ).mappings().all()
    return [dict(r) for r in rows]
