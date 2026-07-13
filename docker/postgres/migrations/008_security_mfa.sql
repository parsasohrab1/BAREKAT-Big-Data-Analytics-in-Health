-- MFA and security hardening schema

CREATE TABLE IF NOT EXISTS audit.user_mfa (
    username        VARCHAR(100) PRIMARY KEY,
    totp_secret     TEXT NOT NULL,
    mfa_enabled     BOOLEAN DEFAULT FALSE,
    enrolled_at     TIMESTAMPTZ DEFAULT NOW(),
    last_verified   TIMESTAMPTZ
);

-- Track PHI encryption migration status
CREATE TABLE IF NOT EXISTS audit.phi_encryption_log (
    log_id          BIGSERIAL PRIMARY KEY,
    table_name      VARCHAR(100) NOT NULL,
    column_name     VARCHAR(100) NOT NULL,
    records_encrypted INTEGER DEFAULT 0,
    encrypted_at    TIMESTAMPTZ DEFAULT NOW(),
    triggered_by    VARCHAR(100)
);
