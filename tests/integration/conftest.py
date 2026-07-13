"""Fixtures for integration tests (PostgreSQL + API)."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine


@pytest.fixture(scope="session")
def integration_env(tmp_path_factory):
    """Configure environment and database for integration tests."""
    data_dir = tmp_path_factory.mktemp("integration_data")
    raw_dir = data_dir / "raw"
    raw_dir.mkdir()
    models_dir = data_dir / "models"
    models_dir.mkdir()

    os.environ["BAREKAT_ENV"] = "test"
    os.environ["POSTGRES_HOST"] = os.getenv("POSTGRES_HOST", "localhost")
    os.environ["POSTGRES_PORT"] = os.getenv("POSTGRES_PORT", "5432")
    os.environ["POSTGRES_USER"] = os.getenv("POSTGRES_USER", "barekat")
    os.environ["POSTGRES_PASSWORD"] = os.getenv("POSTGRES_PASSWORD", "barekat_secret")
    os.environ["POSTGRES_DB"] = os.getenv("POSTGRES_DB", "barekat_health_test")
    os.environ["DATA_RAW_PATH"] = str(raw_dir)
    os.environ["DATA_MODELS_PATH"] = str(models_dir)
    os.environ["JWT_SECRET"] = "test-jwt-secret"

    from barekat.config.settings import get_settings

    get_settings.cache_clear()

    db_url = (
        f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}/{os.environ['POSTGRES_DB']}"
    )

    try:
        from scripts.apply_init_sql import apply_init_sql

        apply_init_sql()
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available for integration tests: {exc}")

    engine = create_engine(db_url)
    import barekat.storage.database as db_module

    db_module.engine = engine
    db_module.SessionLocal.configure(bind=engine)
    get_settings.cache_clear()

    _seed_csv_data(raw_dir)

    from barekat.etl.pipeline import ETLPipeline

    ETLPipeline().run(mode="incremental", skip_validation=True)

    yield {
        "engine": engine,
        "raw_dir": raw_dir,
        "models_dir": models_dir,
        "db_url": db_url,
    }

    engine.dispose()
    get_settings.cache_clear()


def _seed_csv_data(raw_dir: Path) -> None:
    """Write minimal synthetic CSV files for ETL tests."""
    patients = pd.DataFrame({
        "Patient_ID": ["PT00001", "PT00002"],
        "Age": [55, 40],
        "Gender": ["M", "F"],
        "Blood_Type": ["A+", "O+"],
        "BMI": [28.0, 24.0],
        "Smoking_Status": ["Never", "Former"],
        "Diabetes": [1, 0],
        "Hypertension": [1, 0],
    })
    admissions = pd.DataFrame({
        "Admission_ID": ["AD000001", "AD000002"],
        "Patient_ID": ["PT00001", "PT00002"],
        "Admission_Date": pd.to_datetime(["2024-01-10", "2024-02-15"]),
        "Discharge_Date": pd.to_datetime(["2024-01-20", "2024-02-20"]),
        "Department": ["Cardiology", "Pediatrics"],
        "Admission_Type": ["Emergency", "Elective"],
        "Length_of_Stay": [10, 5],
        "ICU_Required": [1, 0],
        "Readmission_Flag": [1, 0],
    })
    diagnoses = pd.DataFrame({
        "Diagnosis_ID": ["DG000001", "DG000002"],
        "Admission_ID": ["AD000001", "AD000002"],
        "ICD_Code": ["I10", "J44.9"],
        "Diagnosis_Description": ["Hypertension", "COPD"],
        "Primary_Diagnosis": [True, True],
    })
    medications = pd.DataFrame({
        "Medication_ID": ["MD000001"],
        "Admission_ID": ["AD000001"],
        "Medication_Name": ["Lisinopril"],
        "Dosage": ["10 mg"],
        "Frequency": ["Daily"],
        "Prescribed_Date": pd.to_datetime(["2024-01-11"]),
    })
    lab_results = pd.DataFrame({
        "Lab_ID": ["LB000001"],
        "Admission_ID": ["AD000001"],
        "Test_Name": ["CBC"],
        "Result_Value": [7.5],
        "Unit": ["mg/dL"],
        "Test_Date": pd.to_datetime(["2024-01-12"]),
        "Abnormal_Flag": [0],
    })

    patients.to_csv(raw_dir / "patients.csv", index=False)
    admissions.to_csv(raw_dir / "admissions.csv", index=False)
    diagnoses.to_csv(raw_dir / "diagnoses.csv", index=False)
    medications.to_csv(raw_dir / "medications.csv", index=False)
    lab_results.to_csv(raw_dir / "lab_results.csv", index=False)


@pytest.fixture
def api_client(integration_env):
    from barekat.api.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def auth_headers(api_client):
    response = api_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
