-- Multi-tenancy: hospitals as isolated tenants with billing/quota

CREATE SCHEMA IF NOT EXISTS tenant;

-- Hospital organizations (tenants)
CREATE TABLE IF NOT EXISTS tenant.tenants (
    tenant_id       VARCHAR(50) PRIMARY KEY,
    slug            VARCHAR(50) UNIQUE NOT NULL,
    name_fa         VARCHAR(200) NOT NULL,
    name_en         VARCHAR(200),
    plan_id         VARCHAR(50) NOT NULL DEFAULT 'starter',
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'suspended', 'trial', 'cancelled')),
    contact_email   VARCHAR(255),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Billing plans
CREATE TABLE IF NOT EXISTS tenant.plans (
    plan_id             VARCHAR(50) PRIMARY KEY,
    name_fa             VARCHAR(100) NOT NULL,
    name_en             VARCHAR(100),
    price_monthly_usd   DECIMAL(10,2) DEFAULT 0,
    quota_patients      INTEGER NOT NULL DEFAULT 10000,
    quota_admissions    INTEGER NOT NULL DEFAULT 50000,
    quota_api_calls     INTEGER NOT NULL DEFAULT 100000,
    quota_storage_gb    INTEGER NOT NULL DEFAULT 50,
    quota_ml_jobs       INTEGER NOT NULL DEFAULT 100,
    features            JSONB DEFAULT '{}',
    is_active           BOOLEAN DEFAULT TRUE
);

INSERT INTO tenant.plans (plan_id, name_fa, name_en, price_monthly_usd, quota_patients, quota_admissions, quota_api_calls, quota_storage_gb, quota_ml_jobs, features) VALUES
    ('starter', 'استارتر', 'Starter', 299, 5000, 20000, 50000, 20, 50,
     '{"ml": true, "fhir": false, "imaging": false, "streaming": false}'),
    ('professional', 'حرفه‌ای', 'Professional', 899, 25000, 100000, 250000, 100, 200,
     '{"ml": true, "fhir": true, "imaging": true, "streaming": false}'),
    ('enterprise', 'سازمانی', 'Enterprise', 2499, 100000, 500000, 1000000, 500, 1000,
     '{"ml": true, "fhir": true, "imaging": true, "streaming": true, "compliance": true}')
ON CONFLICT (plan_id) DO NOTHING;

-- Per-tenant dashboard & feature settings
CREATE TABLE IF NOT EXISTS tenant.tenant_settings (
    tenant_id           VARCHAR(50) PRIMARY KEY REFERENCES tenant.tenants(tenant_id),
    logo_url            TEXT,
    primary_color       VARCHAR(20) DEFAULT '#0891B2',
    locale              VARCHAR(10) DEFAULT 'fa',
    timezone            VARCHAR(50) DEFAULT 'Asia/Tehran',
    enabled_pages       JSONB DEFAULT '["overview","patients","admissions","ml","alerts"]',
    custom_thresholds   JSONB DEFAULT '{}',
    fhir_profile        VARCHAR(50) DEFAULT 'iran_moh',
    dashboard_title     VARCHAR(200),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- User ↔ tenant membership
CREATE TABLE IF NOT EXISTS tenant.tenant_users (
    membership_id   SERIAL PRIMARY KEY,
    tenant_id       VARCHAR(50) NOT NULL REFERENCES tenant.tenants(tenant_id),
    username        VARCHAR(100) NOT NULL,
    role            VARCHAR(50) NOT NULL DEFAULT 'clinician',
    is_primary      BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (tenant_id, username)
);

-- Usage metering (billing)
CREATE TABLE IF NOT EXISTS tenant.usage_records (
    record_id       BIGSERIAL PRIMARY KEY,
    tenant_id       VARCHAR(50) NOT NULL REFERENCES tenant.tenants(tenant_id),
    metric          VARCHAR(50) NOT NULL,
    quantity        BIGINT NOT NULL DEFAULT 1,
    recorded_at     TIMESTAMPTZ DEFAULT NOW(),
    metadata        JSONB
);

CREATE INDEX IF NOT EXISTS idx_usage_tenant_metric ON tenant.usage_records(tenant_id, metric, recorded_at DESC);

-- Monthly usage aggregates for billing
CREATE TABLE IF NOT EXISTS tenant.usage_summary (
    tenant_id       VARCHAR(50) NOT NULL REFERENCES tenant.tenants(tenant_id),
    period_month    DATE NOT NULL,
    metric          VARCHAR(50) NOT NULL,
    total_quantity  BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, period_month, metric)
);

-- Seed demo tenants
INSERT INTO tenant.tenants (tenant_id, slug, name_fa, name_en, plan_id, contact_email) VALUES
    ('default', 'default', 'بیمارستان پیش‌فرض', 'Default Hospital', 'professional', 'admin@default.local'),
    ('tehran-general', 'tehran-general', 'بیمارستان عمومی تهران', 'Tehran General Hospital', 'enterprise', 'it@tehran-general.ir'),
    ('isfahan-medical', 'isfahan-medical', 'مرکز پزشکی اصفهان', 'Isfahan Medical Center', 'professional', 'admin@isfahan-medical.ir'),
    ('mashhad-university', 'mashhad-university', 'بیمارستان دانشگاهی مشهد', 'Mashhad University Hospital', 'starter', 'info@mashhad-uni.ir')
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO tenant.tenant_settings (tenant_id, dashboard_title, primary_color, enabled_pages) VALUES
    ('default', 'BAREKAT — بیمارستان پیش‌فرض', '#0891B2', '["overview","patients","admissions","diagnoses","medications","laboratory","ml","alerts","imaging","compliance"]'),
    ('tehran-general', 'بیمارستان عمومی تهران', '#0D9488', '["overview","patients","admissions","ml","alerts","imaging","compliance"]'),
    ('isfahan-medical', 'مرکز پزشکی اصفهان', '#7C3AED', '["overview","patients","admissions","diagnoses","ml","alerts"]'),
    ('mashhad-university', 'بیمارستان دانشگاهی مشهد', '#DC2626', '["overview","patients","admissions","alerts"]')
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO tenant.tenant_users (tenant_id, username, role, is_primary) VALUES
    ('default', 'admin', 'admin', TRUE),
    ('default', 'clinician', 'clinician', TRUE),
    ('default', 'researcher', 'researcher', TRUE),
    ('tehran-general', 'admin', 'admin', TRUE),
    ('isfahan-medical', 'clinician', 'clinician', TRUE)
ON CONFLICT (tenant_id, username) DO NOTHING;

-- Add tenant_id to clinical data tables (row-level isolation)
ALTER TABLE raw.patients ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50) NOT NULL DEFAULT 'default';
ALTER TABLE raw.admissions ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50) NOT NULL DEFAULT 'default';
ALTER TABLE raw.diagnoses ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50) NOT NULL DEFAULT 'default';
ALTER TABLE raw.medications ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50) NOT NULL DEFAULT 'default';
ALTER TABLE raw.lab_results ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50) NOT NULL DEFAULT 'default';
ALTER TABLE raw.clinical_notes ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50) NOT NULL DEFAULT 'default';
ALTER TABLE raw.vital_signs ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50) NOT NULL DEFAULT 'default';
ALTER TABLE raw.dicom_studies ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50) NOT NULL DEFAULT 'default';
ALTER TABLE analytics.predictive_alerts ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50) NOT NULL DEFAULT 'default';
ALTER TABLE analytics.admission_summary ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50) NOT NULL DEFAULT 'default';
ALTER TABLE audit.access_logs ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_patients_tenant ON raw.patients(tenant_id);
CREATE INDEX IF NOT EXISTS idx_admissions_tenant ON raw.admissions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_alerts_tenant ON analytics.predictive_alerts(tenant_id);

-- FK to tenants (nullable for legacy rows during migration)
DO $$ BEGIN
    ALTER TABLE raw.patients
        ADD CONSTRAINT fk_patients_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenant.tenants(tenant_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
