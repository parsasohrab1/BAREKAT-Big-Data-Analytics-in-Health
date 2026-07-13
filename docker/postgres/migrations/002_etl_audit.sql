-- Migration 002: ETL audit and watermarks (for existing databases)
CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS audit.etl_runs (
    run_id              BIGSERIAL PRIMARY KEY,
    pipeline_name       VARCHAR(100) NOT NULL DEFAULT 'health_etl',
    status              VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'success', 'failed', 'retrying')),
    mode                VARCHAR(20) NOT NULL DEFAULT 'incremental'
                        CHECK (mode IN ('full', 'incremental')),
    started_at          TIMESTAMPTZ DEFAULT NOW(),
    finished_at         TIMESTAMPTZ,
    records_loaded      JSONB,
    validation_result   JSONB,
    quality_checks      JSONB,
    error_message       TEXT,
    retry_count         INTEGER DEFAULT 0,
    celery_task_id      VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_etl_runs_status ON audit.etl_runs(status);
CREATE INDEX IF NOT EXISTS idx_etl_runs_started ON audit.etl_runs(started_at DESC);

CREATE TABLE IF NOT EXISTS staging.etl_watermarks (
    table_name          VARCHAR(100) PRIMARY KEY,
    last_loaded_at      TIMESTAMPTZ DEFAULT NOW(),
    last_record_id      VARCHAR(50),
    record_count        BIGINT DEFAULT 0
);
