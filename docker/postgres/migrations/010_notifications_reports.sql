-- Notifications, weekly reports, and PWA preferences

CREATE SCHEMA IF NOT EXISTS reports;

CREATE TABLE IF NOT EXISTS tenant.notification_preferences (
    pref_id       SERIAL PRIMARY KEY,
    tenant_id     VARCHAR(50) NOT NULL REFERENCES tenant.tenants(tenant_id) ON DELETE CASCADE,
    user_email    VARCHAR(255),
    phone         VARCHAR(20),
    email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sms_enabled   BOOLEAN NOT NULL DEFAULT TRUE,
    alert_min_severity VARCHAR(20) NOT NULL DEFAULT 'critical'
        CHECK (alert_min_severity IN ('low', 'medium', 'high', 'critical')),
    weekly_report BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, user_email)
);

CREATE TABLE IF NOT EXISTS reports.weekly_archives (
    report_id     BIGSERIAL PRIMARY KEY,
    tenant_id     VARCHAR(50) NOT NULL,
    period_start  DATE NOT NULL,
    period_end    DATE NOT NULL,
    excel_path    TEXT,
    pdf_path      TEXT,
    metrics       JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_weekly_archives_tenant ON reports.weekly_archives(tenant_id, period_end DESC);

CREATE TABLE IF NOT EXISTS audit.notification_log (
    log_id            BIGSERIAL PRIMARY KEY,
    tenant_id         VARCHAR(50),
    channel           VARCHAR(20) NOT NULL CHECK (channel IN ('email', 'sms')),
    recipient_masked  VARCHAR(100),
    subject           TEXT,
    alert_id          VARCHAR(50),
    severity          VARCHAR(20),
    status            VARCHAR(20) NOT NULL DEFAULT 'sent'
        CHECK (status IN ('sent', 'failed', 'skipped', 'queued')),
    error_message     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notification_log_tenant ON audit.notification_log(tenant_id, created_at DESC);

-- Seed manager notification prefs for demo tenants
INSERT INTO tenant.notification_preferences (tenant_id, user_email, phone, weekly_report)
VALUES
    ('default', 'admin@barekat.local', '09120000001', TRUE),
    ('tehran-general', 'manager@tehran-hospital.ir', '09121234567', TRUE),
    ('isfahan-medical', 'manager@isfahan-med.ir', '09131234567', TRUE)
ON CONFLICT (tenant_id, user_email) DO NOTHING;
