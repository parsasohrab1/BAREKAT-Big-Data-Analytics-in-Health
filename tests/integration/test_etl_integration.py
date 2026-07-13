"""Integration tests for ETL pipeline against PostgreSQL."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from barekat.etl.pipeline import ETLPipeline
from barekat.storage.database import engine

pytestmark = pytest.mark.integration


def test_etl_incremental_load(integration_env):
    pipeline = ETLPipeline()
    result = pipeline.run(mode="incremental", skip_validation=True)

    assert result["status"] == "success"
    assert result["records_loaded"]["patients"] >= 2

    with engine.connect() as conn:
        patient_count = conn.execute(text("SELECT COUNT(*) FROM raw.patients")).scalar()
        admission_count = conn.execute(text("SELECT COUNT(*) FROM raw.admissions")).scalar()
        run_count = conn.execute(text("SELECT COUNT(*) FROM audit.etl_runs WHERE status = 'success'")).scalar()

    assert patient_count >= 2
    assert admission_count >= 2
    assert run_count >= 1


def test_etl_audit_log_contains_run(integration_env):
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT mode, status FROM audit.etl_runs
            ORDER BY started_at DESC LIMIT 1
        """)).mappings().first()

    assert row is not None
    assert row["status"] == "success"
    assert row["mode"] in ("incremental", "full")
