"""PostgreSQL data access for the dashboard."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from barekat.config.settings import get_settings
from barekat.storage.database import engine

TABLE_QUERIES = {
    "patients": "SELECT * FROM raw.patients WHERE tenant_id = :tenant_id ORDER BY patient_id",
    "admissions": "SELECT * FROM raw.admissions WHERE tenant_id = :tenant_id ORDER BY admission_date DESC",
    "diagnoses": "SELECT * FROM raw.diagnoses WHERE tenant_id = :tenant_id ORDER BY admission_id",
    "medications": "SELECT * FROM raw.medications WHERE tenant_id = :tenant_id ORDER BY admission_id",
    "lab_results": "SELECT * FROM raw.lab_results WHERE tenant_id = :tenant_id ORDER BY admission_id",
}

COLUMN_MAP = {
    "patients": {
        "patient_id": "Patient_ID",
        "age": "Age",
        "gender": "Gender",
        "blood_type": "Blood_Type",
        "bmi": "BMI",
        "smoking_status": "Smoking_Status",
        "diabetes": "Diabetes",
        "hypertension": "Hypertension",
    },
    "admissions": {
        "admission_id": "Admission_ID",
        "patient_id": "Patient_ID",
        "admission_date": "Admission_Date",
        "discharge_date": "Discharge_Date",
        "department": "Department",
        "admission_type": "Admission_Type",
        "length_of_stay": "Length_of_Stay",
        "icu_required": "ICU_Required",
        "readmission_flag": "Readmission_Flag",
    },
    "diagnoses": {
        "diagnosis_id": "Diagnosis_ID",
        "admission_id": "Admission_ID",
        "icd_code": "ICD_Code",
        "diagnosis_description": "Diagnosis_Description",
        "primary_diagnosis": "Primary_Diagnosis",
    },
    "medications": {
        "medication_id": "Medication_ID",
        "admission_id": "Admission_ID",
        "medication_name": "Medication_Name",
        "dosage": "Dosage",
        "frequency": "Frequency",
        "prescribed_date": "Prescribed_Date",
    },
    "lab_results": {
        "lab_id": "Lab_ID",
        "admission_id": "Admission_ID",
        "test_name": "Test_Name",
        "result_value": "Result_Value",
        "unit": "Unit",
        "test_date": "Test_Date",
        "abnormal_flag": "Abnormal_Flag",
    },
}


def postgres_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def postgres_has_data() -> bool:
    try:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM raw.patients")).scalar()
        return bool(count and count > 0)
    except Exception:
        return False


def _to_dashboard_df(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    mapping = COLUMN_MAP.get(table_name, {})
    result = df.rename(columns=mapping)
    drop_cols = [c for c in ("created_at", "updated_at") if c in result.columns]
    if drop_cols:
        result = result.drop(columns=drop_cols)
    return result


def load_tables_from_postgres(tenant_id: str | None = None) -> dict[str, pd.DataFrame]:
    from barekat.tenant.context import get_tenant_id

    tid = tenant_id or get_tenant_id()
    tables: dict[str, pd.DataFrame] = {}
    with engine.connect() as conn:
        for name, query in TABLE_QUERIES.items():
            df = pd.read_sql(text(query), conn, params={"tenant_id": tid})
            if df.empty:
                continue
            tables[name] = _to_dashboard_df(df, name)
    return tables


def get_data_source_label() -> str:
    settings = get_settings()
    source = getattr(settings, "dashboard_data_source", "auto")
    if source == "csv":
        return "CSV"
    if source == "postgres":
        return "PostgreSQL"
    if postgres_has_data():
        return "PostgreSQL"
    return "CSV"
