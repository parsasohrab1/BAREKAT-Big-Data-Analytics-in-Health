-- Advanced ML: clinical notes, vital signs, outcome flags

ALTER TABLE raw.admissions
    ADD COLUMN IF NOT EXISTS mortality_flag BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS sepsis_flag BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS raw.clinical_notes (
    note_id         VARCHAR(20) PRIMARY KEY,
    admission_id    VARCHAR(20) NOT NULL REFERENCES raw.admissions(admission_id),
    note_type       VARCHAR(50) DEFAULT 'progress',
    note_text       TEXT NOT NULL,
    authored_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clinical_notes_admission ON raw.clinical_notes(admission_id);

CREATE TABLE IF NOT EXISTS raw.vital_signs (
    vital_id        VARCHAR(20) PRIMARY KEY,
    admission_id    VARCHAR(20) NOT NULL REFERENCES raw.admissions(admission_id),
    heart_rate      INTEGER,
    respiratory_rate INTEGER,
    systolic_bp     INTEGER,
    diastolic_bp    INTEGER,
    temperature_c   DECIMAL(4,1),
    spo2            INTEGER,
    lactate         DECIMAL(5,2),
    recorded_at     TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vital_signs_admission ON raw.vital_signs(admission_id);
CREATE INDEX IF NOT EXISTS idx_vital_signs_recorded ON raw.vital_signs(recorded_at);

ALTER TABLE analytics.admission_summary
    ADD COLUMN IF NOT EXISTS predicted_los DECIMAL(6,2),
    ADD COLUMN IF NOT EXISTS mortality_risk DECIMAL(5,4),
    ADD COLUMN IF NOT EXISTS sepsis_risk DECIMAL(5,4),
    ADD COLUMN IF NOT EXISTS deterioration_score DECIMAL(5,4);
