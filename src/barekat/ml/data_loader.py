"""Load training data from PostgreSQL or CSV."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import text

from barekat.config.settings import get_settings
from barekat.ingestion.csv_loader import CSVIngestor
from barekat.storage.database import engine

TABLE_MAP = {
    "patients": "Patients",
    "admissions": "Admissions",
    "diagnoses": "Diagnoses",
    "medications": "Medications",
    "lab_results": "Lab_Results",
    "clinical_notes": "Clinical_Notes",
    "vital_signs": "Vital_Signs",
}

COLUMN_MAP = {
    "patients": {
        "patient_id": "Patient_ID", "age": "Age", "gender": "Gender",
        "blood_type": "Blood_Type", "bmi": "BMI", "smoking_status": "Smoking_Status",
        "diabetes": "Diabetes", "hypertension": "Hypertension",
    },
    "admissions": {
        "admission_id": "Admission_ID", "patient_id": "Patient_ID",
        "admission_date": "Admission_Date", "discharge_date": "Discharge_Date",
        "department": "Department", "admission_type": "Admission_Type",
        "length_of_stay": "Length_of_Stay", "icu_required": "ICU_Required",
        "readmission_flag": "Readmission_Flag",
        "mortality_flag": "Mortality_Flag", "sepsis_flag": "Sepsis_Flag",
    },
    "diagnoses": {
        "diagnosis_id": "Diagnosis_ID", "admission_id": "Admission_ID",
        "icd_code": "ICD_Code", "diagnosis_description": "Diagnosis_Description",
        "primary_diagnosis": "Primary_Diagnosis",
    },
    "medications": {
        "medication_id": "Medication_ID", "admission_id": "Admission_ID",
        "medication_name": "Medication_Name", "dosage": "Dosage",
        "frequency": "Frequency", "prescribed_date": "Prescribed_Date",
    },
    "lab_results": {
        "lab_id": "Lab_ID", "admission_id": "Admission_ID", "test_name": "Test_Name",
        "result_value": "Result_Value", "unit": "Unit", "test_date": "Test_Date",
        "abnormal_flag": "Abnormal_Flag",
    },
    "clinical_notes": {
        "note_id": "Note_ID", "admission_id": "Admission_ID", "note_type": "Note_Type",
        "note_text": "Note_Text", "authored_at": "Authored_At",
    },
    "vital_signs": {
        "vital_id": "Vital_ID", "admission_id": "Admission_ID",
        "heart_rate": "Heart_Rate", "respiratory_rate": "Respiratory_Rate",
        "systolic_bp": "Systolic_BP", "diastolic_bp": "Diastolic_BP",
        "temperature_c": "Temperature_C", "spo2": "SpO2", "lactate": "Lactate",
        "recorded_at": "Recorded_At",
    },
}


def _postgres_has_data() -> bool:
    try:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM raw.patients")).scalar()
        return bool(count and count > 0)
    except Exception:
        return False


def load_from_postgres() -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    queries = {
        "patients": "SELECT * FROM raw.patients",
        "admissions": "SELECT * FROM raw.admissions",
        "diagnoses": "SELECT * FROM raw.diagnoses",
        "medications": "SELECT * FROM raw.medications",
        "lab_results": "SELECT * FROM raw.lab_results",
        "clinical_notes": "SELECT * FROM raw.clinical_notes",
        "vital_signs": "SELECT * FROM raw.vital_signs",
    }
    with engine.connect() as conn:
        for name, query in queries.items():
            try:
                df = pd.read_sql(text(query), conn)
            except Exception:
                if name in ("clinical_notes", "vital_signs"):
                    continue
                raise
            if df.empty:
                continue
            mapping = COLUMN_MAP.get(name, {})
            df = df.rename(columns=mapping)
            drop_cols = [c for c in ("created_at", "updated_at") if c in df.columns]
            if drop_cols:
                df = df.drop(columns=drop_cols)
            if name == "clinical_notes" and "Note_Text" in df.columns:
                from barekat.security.phi_crypto import decrypt_phi
                df["Note_Text"] = df["Note_Text"].apply(decrypt_phi)
            tables[TABLE_MAP[name]] = df
    return tables


def load_from_csv() -> dict[str, pd.DataFrame]:
    settings = get_settings()
    ingestor = CSVIngestor(Path(settings.data_raw_path))
    raw = ingestor.load_all()
    return {TABLE_MAP[k]: v for k, v in raw.items()}


def load_training_data(prefer_postgres: bool = True) -> dict[str, pd.DataFrame]:
    if prefer_postgres and _postgres_has_data():
        try:
            data = load_from_postgres()
            if data:
                return data
        except Exception:
            pass
    return load_from_csv()
