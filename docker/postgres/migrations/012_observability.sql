-- Observability: model drift event history

CREATE SCHEMA IF NOT EXISTS observability;

CREATE TABLE IF NOT EXISTS observability.drift_events (
    event_id        BIGSERIAL PRIMARY KEY,
    model_name      VARCHAR(100) NOT NULL,
    auc_drop        DECIMAL(6,4),
    psi             DECIMAL(8,4),
    drift_detected  BOOLEAN NOT NULL DEFAULT FALSE,
    details         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_drift_events_model ON observability.drift_events(model_name, created_at DESC);
