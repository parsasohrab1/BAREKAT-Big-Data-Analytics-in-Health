-- Data Lake metadata: Bronze / Silver / Gold on MinIO

CREATE SCHEMA IF NOT EXISTS lake;

CREATE TABLE IF NOT EXISTS lake.table_registry (
    table_id        SERIAL PRIMARY KEY,
    layer           VARCHAR(10) NOT NULL CHECK (layer IN ('bronze', 'silver', 'gold')),
    table_name      VARCHAR(100) NOT NULL,
    format          VARCHAR(20) NOT NULL DEFAULT 'parquet'
                    CHECK (format IN ('parquet', 'delta', 'iceberg')),
    storage_path    TEXT NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    schema_version  INTEGER NOT NULL DEFAULT 1,
    row_count       BIGINT,
    last_commit_at  TIMESTAMPTZ,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (layer, table_name)
);

CREATE TABLE IF NOT EXISTS lake.job_runs (
    run_id              BIGSERIAL PRIMARY KEY,
    job_name            VARCHAR(100) NOT NULL,
    layer               VARCHAR(10),
    status              VARCHAR(20) NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running', 'success', 'failed')),
    records_processed   BIGINT,
    tables_processed    TEXT[],
    error_message       TEXT,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_lake_job_runs_started ON lake.job_runs(started_at DESC);

-- Seed registry for core health tables
INSERT INTO lake.table_registry (layer, table_name, format, storage_path, metadata) VALUES
    ('bronze', 'patients',       'parquet', 'bronze/csv/patients',       '{"source": "csv"}'),
    ('bronze', 'admissions',     'parquet', 'bronze/csv/admissions',     '{"source": "csv"}'),
    ('bronze', 'diagnoses',      'parquet', 'bronze/csv/diagnoses',      '{"source": "csv"}'),
    ('bronze', 'medications',    'parquet', 'bronze/csv/medications',    '{"source": "csv"}'),
    ('bronze', 'lab_results',    'parquet', 'bronze/csv/lab_results',    '{"source": "csv"}'),
    ('bronze', 'clinical_notes', 'parquet', 'bronze/csv/clinical_notes', '{"source": "csv"}'),
    ('bronze', 'vital_signs',    'parquet', 'bronze/csv/vital_signs',    '{"source": "csv"}'),
    ('bronze', 'stream_events',  'delta',   'bronze/stream/events',      '{"source": "kafka"}'),
    ('silver', 'patients',       'delta',   'silver/health/patients',    '{}'),
    ('silver', 'admissions',     'delta',   'silver/health/admissions',  '{}'),
    ('silver', 'diagnoses',      'delta',   'silver/health/diagnoses',   '{}'),
    ('silver', 'medications',    'delta',   'silver/health/medications', '{}'),
    ('silver', 'lab_results',    'delta',   'silver/health/lab_results', '{}'),
    ('gold',   'admission_summary', 'delta', 'gold/marts/admission_summary', '{}'),
    ('gold',   'department_stats',  'delta', 'gold/marts/department_stats',  '{}'),
    ('gold',   'alert_rollup',      'delta', 'gold/marts/alert_rollup',      '{}')
ON CONFLICT (layer, table_name) DO NOTHING;
