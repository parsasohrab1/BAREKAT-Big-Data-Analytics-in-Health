-- DICOM imaging studies catalog

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
CREATE INDEX IF NOT EXISTS idx_dicom_studies_date ON raw.dicom_studies(study_date DESC);
