-- Seed default users with bcrypt hashes and tenant memberships

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
    email = EXCLUDED.email,
    is_active = TRUE;

-- Ensure tenant schema exists (migration 009 may not have run on older DBs)
CREATE SCHEMA IF NOT EXISTS tenant;

INSERT INTO tenant.tenants (tenant_id, slug, name_fa, name_en, plan_id, contact_email) VALUES
    ('default', 'default', 'بیمارستان پیش‌فرض', 'Default Hospital', 'professional', 'admin@default.local'),
    ('tehran-general', 'tehran-general', 'بیمارستان عمومی تهران', 'Tehran General Hospital', 'enterprise', 'it@tehran-general.ir'),
    ('isfahan-medical', 'isfahan-medical', 'مرکز پزشکی اصفهان', 'Isfahan Medical Center', 'professional', 'admin@isfahan-medical.ir')
ON CONFLICT (tenant_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS tenant.tenant_users (
    membership_id   SERIAL PRIMARY KEY,
    tenant_id       VARCHAR(50) NOT NULL,
    username        VARCHAR(100) NOT NULL,
    role            VARCHAR(50) NOT NULL DEFAULT 'clinician',
    is_primary      BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (tenant_id, username)
);

INSERT INTO tenant.tenant_users (tenant_id, username, role, is_primary) VALUES
    ('default', 'admin', 'platform_admin', TRUE),
    ('tehran-general', 'clinician', 'clinician', TRUE),
    ('isfahan-medical', 'researcher', 'researcher', TRUE)
ON CONFLICT (tenant_id, username) DO UPDATE SET
    role = EXCLUDED.role,
    is_primary = EXCLUDED.is_primary;
