-- Compliance & Privacy: HIPAA / GDPR / domestic regulations
-- Audit trail, retention, pseudonymization, consent

-- Extend access_logs for full audit trail
ALTER TABLE audit.access_logs ADD COLUMN IF NOT EXISTS username VARCHAR(100);
ALTER TABLE audit.access_logs ADD COLUMN IF NOT EXISTS role VARCHAR(50);
ALTER TABLE audit.access_logs ADD COLUMN IF NOT EXISTS http_method VARCHAR(10);
ALTER TABLE audit.access_logs ADD COLUMN IF NOT EXISTS status_code INTEGER;
ALTER TABLE audit.access_logs ADD COLUMN IF NOT EXISTS request_id VARCHAR(64);
ALTER TABLE audit.access_logs ADD COLUMN IF NOT EXISTS user_agent TEXT;
ALTER TABLE audit.access_logs ADD COLUMN IF NOT EXISTS patient_id VARCHAR(20);
ALTER TABLE audit.access_logs ADD COLUMN IF NOT EXISTS resource_type VARCHAR(50);
ALTER TABLE audit.access_logs ADD COLUMN IF NOT EXISTS details JSONB;

CREATE INDEX IF NOT EXISTS idx_access_logs_timestamp ON audit.access_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_access_logs_username ON audit.access_logs(username);
CREATE INDEX IF NOT EXISTS idx_access_logs_patient ON audit.access_logs(patient_id);
CREATE INDEX IF NOT EXISTS idx_access_logs_action ON audit.access_logs(action);

-- Pseudonymization map (reversible with salt — GDPR pseudonymization)
CREATE TABLE IF NOT EXISTS audit.pseudonym_map (
    patient_id          VARCHAR(20) PRIMARY KEY,
    pseudonym_id        VARCHAR(64) UNIQUE NOT NULL,
    algorithm           VARCHAR(50) DEFAULT 'HMAC-SHA256',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    created_by          VARCHAR(100)
);

-- Consent records (GDPR Art. 7 / domestic consent)
CREATE TABLE IF NOT EXISTS audit.consent_records (
    consent_id          BIGSERIAL PRIMARY KEY,
    patient_id          VARCHAR(20) NOT NULL,
    purpose             VARCHAR(200) NOT NULL,
    lawful_basis        VARCHAR(50) NOT NULL
                        CHECK (lawful_basis IN (
                            'consent', 'contract', 'legal_obligation',
                            'vital_interest', 'public_interest', 'legitimate_interest',
                            'treatment', 'research'
                        )),
    granted             BOOLEAN NOT NULL DEFAULT TRUE,
    granted_at          TIMESTAMPTZ DEFAULT NOW(),
    revoked_at          TIMESTAMPTZ,
    recorded_by         VARCHAR(100),
    notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_consent_patient ON audit.consent_records(patient_id);

-- Retention policies per data category
CREATE TABLE IF NOT EXISTS audit.retention_policies (
    policy_id           SERIAL PRIMARY KEY,
    data_category       VARCHAR(100) UNIQUE NOT NULL,
    retention_days      INTEGER NOT NULL CHECK (retention_days > 0),
    regulation_ref      VARCHAR(200),
    auto_purge          BOOLEAN DEFAULT TRUE,
    description_fa      TEXT,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO audit.retention_policies (data_category, retention_days, regulation_ref, description_fa) VALUES
    ('clinical_notes', 2555, 'HIPAA/GDPR/IR-MOH', 'یادداشت‌های بالینی — ۷ سال'),
    ('lab_results', 1825, 'HIPAA/IR-MOH', 'نتایج آزمایش — ۵ سال'),
    ('admissions', 2555, 'HIPAA/GDPR/IR-MOH', 'سوابق بستری — ۷ سال'),
    ('dicom_studies', 3650, 'HIPAA/IR-MOH', 'تصاویر پزشکی — ۱۰ سال'),
    ('access_logs', 2190, 'HIPAA/GDPR', 'لاگ دسترسی — ۶ سال'),
    ('predictive_alerts', 365, 'IR-MOH', 'هشدارهای تحلیلی — ۱ سال')
ON CONFLICT (data_category) DO NOTHING;

-- Legal hold (suspend deletion for litigation/audit)
CREATE TABLE IF NOT EXISTS audit.legal_holds (
    hold_id             SERIAL PRIMARY KEY,
    patient_id          VARCHAR(20),
    data_category       VARCHAR(100),
    reason              TEXT NOT NULL,
    placed_by           VARCHAR(100) NOT NULL,
    placed_at           TIMESTAMPTZ DEFAULT NOW(),
    released_at         TIMESTAMPTZ,
    is_active           BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_legal_holds_patient ON audit.legal_holds(patient_id) WHERE is_active;

-- Deletion / purge job audit
CREATE TABLE IF NOT EXISTS audit.deletion_jobs (
    job_id              BIGSERIAL PRIMARY KEY,
    job_type            VARCHAR(50) NOT NULL
                        CHECK (job_type IN ('retention_purge', 'erasure', 'anonymization')),
    status              VARCHAR(20) NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running', 'success', 'failed', 'partial')),
    triggered_by        VARCHAR(100),
    records_affected    JSONB,
    error_message       TEXT,
    started_at          TIMESTAMPTZ DEFAULT NOW(),
    finished_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_deletion_jobs_started ON audit.deletion_jobs(started_at DESC);

-- Anonymization status per patient
CREATE TABLE IF NOT EXISTS audit.anonymization_status (
    patient_id          VARCHAR(20) PRIMARY KEY,
    status              VARCHAR(20) NOT NULL DEFAULT 'identified'
                        CHECK (status IN ('identified', 'pseudonymized', 'anonymized', 'erased')),
    method              VARCHAR(50),
    processed_at        TIMESTAMPTZ DEFAULT NOW(),
    processed_by        VARCHAR(100)
);
