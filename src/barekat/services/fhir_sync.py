"""FHIR sync persistence and audit logging."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from barekat.storage.database import engine


def persist_raw_records(raw_records: dict[str, list[dict[str, Any]]]) -> int:
    """Upsert FHIR-mapped records into raw.* tables."""
    total = 0
    table_map = {
        "patients": ("raw", "patients", "patient_id"),
        "admissions": ("raw", "admissions", "admission_id"),
        "diagnoses": ("raw", "diagnoses", "diagnosis_id"),
        "lab_results": ("raw", "lab_results", "lab_id"),
    }
    with engine.begin() as conn:
        for key, (schema, table, pk) in table_map.items():
            rows = raw_records.get(key, [])
            if not rows:
                continue
            df = pd.DataFrame(rows)
            df.to_sql(table, conn, schema=schema, if_exists="append", index=False)
            total += len(df)
    return total


def log_sync_run(
    profile_key: str,
    status: str,
    resources_fetched: dict[str, int],
    events_parsed: int,
    errors: list[str],
) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO audit.fhir_sync_runs
                        (profile_key, status, resources_fetched, events_parsed, error_messages)
                    VALUES
                        (:profile_key, :status, :resources_fetched::jsonb, :events_parsed, :errors)
                """),
                {
                    "profile_key": profile_key,
                    "status": status,
                    "resources_fetched": json.dumps(resources_fetched),
                    "events_parsed": events_parsed,
                    "errors": "; ".join(errors) if errors else None,
                },
            )
    except Exception as exc:
        print(f"FHIR sync log skipped: {exc}")
