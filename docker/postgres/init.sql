-- BAREKAT Health Analytics - Database Schema
-- انطباق با ساختار داده‌های بیمارستانی (EHR)

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS audit;

-- جدول بیماران
CREATE TABLE IF NOT EXISTS raw.patients (
    patient_id      VARCHAR(20) PRIMARY KEY,
    age             INTEGER NOT NULL CHECK (age >= 0 AND age <= 150),
    gender          CHAR(1) CHECK (gender IN ('M', 'F', 'O')),
    blood_type      VARCHAR(5),
    bmi             DECIMAL(5,2),
    smoking_status  VARCHAR(20),
    diabetes        BOOLEAN DEFAULT FALSE,
    hypertension    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- جدول بستری‌ها
CREATE TABLE IF NOT EXISTS raw.admissions (
    admission_id        VARCHAR(20) PRIMARY KEY,
    patient_id          VARCHAR(20) NOT NULL REFERENCES raw.patients(patient_id),
    admission_date      TIMESTAMPTZ NOT NULL,
    discharge_date      TIMESTAMPTZ,
    department          VARCHAR(100),
    admission_type      VARCHAR(50),
    length_of_stay      INTEGER,
    icu_required        BOOLEAN DEFAULT FALSE,
    readmission_flag    BOOLEAN DEFAULT FALSE,
    mortality_flag      BOOLEAN DEFAULT FALSE,
    sepsis_flag         BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admissions_patient ON raw.admissions(patient_id);
CREATE INDEX IF NOT EXISTS idx_admissions_date ON raw.admissions(admission_date);

-- جدول تشخیص‌ها (ICD-10)
CREATE TABLE IF NOT EXISTS raw.diagnoses (
    diagnosis_id            VARCHAR(20) PRIMARY KEY,
    admission_id            VARCHAR(20) NOT NULL REFERENCES raw.admissions(admission_id),
    icd_code                VARCHAR(20) NOT NULL,
    diagnosis_description   TEXT,
    primary_diagnosis       BOOLEAN DEFAULT FALSE,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_diagnoses_admission ON raw.diagnoses(admission_id);
CREATE INDEX IF NOT EXISTS idx_diagnoses_icd ON raw.diagnoses(icd_code);

-- جدول داروها
CREATE TABLE IF NOT EXISTS raw.medications (
    medication_id       VARCHAR(20) PRIMARY KEY,
    admission_id        VARCHAR(20) NOT NULL REFERENCES raw.admissions(admission_id),
    medication_name     VARCHAR(200),
    dosage              VARCHAR(50),
    frequency           VARCHAR(20),
    prescribed_date     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_medications_admission ON raw.medications(admission_id);

-- جدول نتایج آزمایشگاهی
CREATE TABLE IF NOT EXISTS raw.lab_results (
    lab_id          VARCHAR(20) PRIMARY KEY,
    admission_id    VARCHAR(20) NOT NULL REFERENCES raw.admissions(admission_id),
    test_name       VARCHAR(100),
    result_value    DECIMAL(12,4),
    unit            VARCHAR(20),
    test_date       TIMESTAMPTZ,
    abnormal_flag   BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lab_results_admission ON raw.lab_results(admission_id);

-- یادداشت‌های بالینی (NLP)
CREATE TABLE IF NOT EXISTS raw.clinical_notes (
    note_id         VARCHAR(20) PRIMARY KEY,
    admission_id    VARCHAR(20) NOT NULL REFERENCES raw.admissions(admission_id),
    note_type       VARCHAR(50) DEFAULT 'progress',
    note_text       TEXT NOT NULL,
    authored_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clinical_notes_admission ON raw.clinical_notes(admission_id);

-- علائم حیاتی (time-series)
CREATE TABLE IF NOT EXISTS raw.vital_signs (
    vital_id            VARCHAR(20) PRIMARY KEY,
    admission_id        VARCHAR(20) NOT NULL REFERENCES raw.admissions(admission_id),
    heart_rate          INTEGER,
    respiratory_rate    INTEGER,
    systolic_bp         INTEGER,
    diastolic_bp        INTEGER,
    temperature_c       DECIMAL(4,1),
    spo2                INTEGER,
    lactate             DECIMAL(5,2),
    recorded_at         TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vital_signs_admission ON raw.vital_signs(admission_id);
CREATE INDEX IF NOT EXISTS idx_vital_signs_recorded ON raw.vital_signs(recorded_at);

-- کاتالوگ مطالعات DICOM (PACS)
CREATE TABLE IF NOT EXISTS raw.dicom_studies (
    study_id            SERIAL PRIMARY KEY,
    study_uid           VARCHAR(128) UNIQUE NOT NULL,
    series_uid          VARCHAR(128),
    patient_id          VARCHAR(20),
    modality            VARCHAR(20),
    study_date          DATE,
    body_part           VARCHAR(100),
    study_description   TEXT,
    instance_count      INTEGER DEFAULT 1,
    storage_path        TEXT,
    thumbnail_path      TEXT,
    pacs_source         VARCHAR(100),
    retrieved_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dicom_studies_patient ON raw.dicom_studies(patient_id);
CREATE INDEX IF NOT EXISTS idx_dicom_studies_modality ON raw.dicom_studies(modality);

-- جدول کاربران و نقش‌ها (RBAC)
CREATE TABLE IF NOT EXISTS audit.users (
    user_id         SERIAL PRIMARY KEY,
    username        VARCHAR(100) UNIQUE NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(50) NOT NULL DEFAULT 'researcher'
                    CHECK (role IN ('admin', 'clinician', 'researcher', 'viewer')),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- لاگ دسترسی (HIPAA/GDPR compliance)
CREATE TABLE IF NOT EXISTS audit.access_logs (
    log_id          BIGSERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES audit.users(user_id),
    username        VARCHAR(100),
    role            VARCHAR(50),
    action          VARCHAR(100) NOT NULL,
    resource        VARCHAR(255),
    resource_type   VARCHAR(50),
    patient_id      VARCHAR(20),
    http_method     VARCHAR(10),
    status_code     INTEGER,
    request_id      VARCHAR(64),
    user_agent      TEXT,
    ip_address      INET,
    details         JSONB,
    timestamp       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_access_logs_timestamp ON audit.access_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_access_logs_username ON audit.access_logs(username);
CREATE INDEX IF NOT EXISTS idx_access_logs_patient ON audit.access_logs(patient_id);

CREATE TABLE IF NOT EXISTS audit.pseudonym_map (
    patient_id          VARCHAR(20) PRIMARY KEY,
    pseudonym_id        VARCHAR(64) UNIQUE NOT NULL,
    algorithm           VARCHAR(50) DEFAULT 'HMAC-SHA256',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    created_by          VARCHAR(100)
);

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

CREATE TABLE IF NOT EXISTS audit.anonymization_status (
    patient_id          VARCHAR(20) PRIMARY KEY,
    status              VARCHAR(20) NOT NULL DEFAULT 'identified'
                        CHECK (status IN ('identified', 'pseudonymized', 'anonymized', 'erased')),
    method              VARCHAR(50),
    processed_at        TIMESTAMPTZ DEFAULT NOW(),
    processed_by        VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS audit.user_mfa (
    username        VARCHAR(100) PRIMARY KEY,
    totp_secret     TEXT NOT NULL,
    mfa_enabled     BOOLEAN DEFAULT FALSE,
    enrolled_at     TIMESTAMPTZ DEFAULT NOW(),
    last_verified   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit.phi_encryption_log (
    log_id              BIGSERIAL PRIMARY KEY,
    table_name          VARCHAR(100) NOT NULL,
    column_name         VARCHAR(100) NOT NULL,
    records_encrypted   INTEGER DEFAULT 0,
    encrypted_at        TIMESTAMPTZ DEFAULT NOW(),
    triggered_by        VARCHAR(100)
);

-- جدول تحلیلی: خلاصه بستری‌ها
CREATE TABLE IF NOT EXISTS analytics.admission_summary (
    admission_id        VARCHAR(20) PRIMARY KEY,
    patient_id          VARCHAR(20),
    department          VARCHAR(100),
    length_of_stay      INTEGER,
    diagnosis_count     INTEGER,
    medication_count    INTEGER,
    lab_test_count      INTEGER,
    readmission_risk    DECIMAL(5,4),
    patient_cluster     INTEGER,
    predicted_los       DECIMAL(6,2),
    mortality_risk      DECIMAL(5,4),
    sepsis_risk         DECIMAL(5,4),
    deterioration_score DECIMAL(5,4),
    computed_at         TIMESTAMPTZ DEFAULT NOW()
);

-- جدول هشدارهای پیش‌بینی‌کننده
CREATE TABLE IF NOT EXISTS analytics.predictive_alerts (
    alert_id        BIGSERIAL PRIMARY KEY,
    patient_id      VARCHAR(20),
    admission_id    VARCHAR(20),
    alert_type      VARCHAR(100) NOT NULL,
    severity        VARCHAR(20) CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    message         TEXT,
    risk_score      DECIMAL(5,4),
    is_acknowledged BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_severity ON analytics.predictive_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON analytics.predictive_alerts(created_at);

-- ETL execution audit log
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

-- ML model registry
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

CREATE TABLE IF NOT EXISTS analytics.department_risk_thresholds (
    department      VARCHAR(100) PRIMARY KEY,
    risk_threshold  DECIMAL(5,4) NOT NULL CHECK (risk_threshold >= 0 AND risk_threshold <= 1),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

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

-- FHIR sync audit log
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

-- Incremental load watermarks
CREATE TABLE IF NOT EXISTS staging.etl_watermarks (
    table_name          VARCHAR(100) PRIMARY KEY,
    last_loaded_at      TIMESTAMPTZ DEFAULT NOW(),
    last_record_id      VARCHAR(50),
    record_count        BIGINT DEFAULT 0
);

-- کاربران پیش‌فرض (رمزها: admin123 / clinician123 / researcher123 — فقط توسعه)
INSERT INTO audit.users (username, email, password_hash, role) VALUES
    (
        'admin',
        'admin@barekat.local',
        '$2b$12$H8QGWF3bM/S.MkPqnoBMheU7GC/UZV5l18szZ9aopiFxMQgA9CQdm',
        'admin'
    ),
    (
        'clinician',
        'clinician@barekat.local',
        '$2b$12$u/25zv8N7x.cGbrXTkij.eDR66NKOSm8ltDxR4BTeS5AGpcgivYBu',
        'clinician'
    ),
    (
        'researcher',
        'researcher@barekat.local',
        '$2b$12$fqyejbdrVdtf.p1fZWmhDeqtB./gYBVit.WRQew//gUFjEfHb3mhK',
        'researcher'
    )
ON CONFLICT (username) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    role = EXCLUDED.role,
    is_active = TRUE;
