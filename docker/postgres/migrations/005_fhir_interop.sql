-- FHIR interoperability audit log

CREATE TABLE IF NOT EXISTS audit.fhir_sync_runs (
    run_id              BIGSERIAL PRIMARY KEY,
    profile_key         VARCHAR(50) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'success', 'partial', 'failed')),
    resources_fetched   JSONB,
    events_parsed       INTEGER DEFAULT 0,
    error_messages      TEXT,
    started_at          TIMESTAMPTZ DEFAULT NOW(),
    finished_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fhir_sync_profile ON audit.fhir_sync_runs(profile_key);
CREATE INDEX IF NOT EXISTS idx_fhir_sync_started ON audit.fhir_sync_runs(started_at DESC);
