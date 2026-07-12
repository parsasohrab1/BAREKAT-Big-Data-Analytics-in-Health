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
    action          VARCHAR(100) NOT NULL,
    resource        VARCHAR(255),
    ip_address      INET,
    timestamp       TIMESTAMPTZ DEFAULT NOW()
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

-- کاربر پیش‌فرض (رمز: admin123 - فقط برای توسعه)
INSERT INTO audit.users (username, email, password_hash, role)
VALUES (
    'admin',
    'admin@barekat.local',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.G2oQKqKqKqKqKq',
    'admin'
) ON CONFLICT (username) DO NOTHING;
