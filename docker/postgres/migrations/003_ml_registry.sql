-- Migration 003: ML model registry and department risk thresholds

CREATE TABLE IF NOT EXISTS analytics.ml_model_registry (
    model_id        BIGSERIAL PRIMARY KEY,
    model_name      VARCHAR(100) NOT NULL,
    version         VARCHAR(50) NOT NULL,
    artifact_path   TEXT NOT NULL,
    is_active       BOOLEAN DEFAULT FALSE,
    metrics         JSONB,
    calibration     JSONB,
    samples         INTEGER,
    trained_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (model_name, version)
);

CREATE INDEX IF NOT EXISTS idx_ml_registry_active ON analytics.ml_model_registry(model_name, is_active);
CREATE INDEX IF NOT EXISTS idx_ml_registry_trained ON analytics.ml_model_registry(trained_at DESC);

CREATE TABLE IF NOT EXISTS analytics.department_risk_thresholds (
    department      VARCHAR(100) PRIMARY KEY,
    risk_threshold  DECIMAL(5,4) NOT NULL CHECK (risk_threshold >= 0 AND risk_threshold <= 1),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- آستانه‌های پیش‌فرض per-department
INSERT INTO analytics.department_risk_thresholds (department, risk_threshold) VALUES
    ('Cardiology', 0.75),
    ('Neurology', 0.70),
    ('Oncology', 0.72),
    ('Orthopedics', 0.68),
    ('Internal Medicine', 0.70),
    ('Pediatrics', 0.65),
    ('Surgery', 0.73),
    ('Psychiatry', 0.68)
ON CONFLICT (department) DO NOTHING;
