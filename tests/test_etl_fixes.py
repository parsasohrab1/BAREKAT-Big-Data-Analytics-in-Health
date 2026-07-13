"""Tests for data alignment and ETL robustness fixes."""

import pandas as pd
import pytest

from barekat.etl.transformers import DataTransformer
from barekat.ingestion.csv_loader import CSVIngestor
from dashboards.utils.ml_analytics import build_alerts


def test_build_alerts_aligns_by_index_not_position():
    master = pd.DataFrame(
        {"Patient_ID": ["P1", "P2", "P3"], "Admission_ID": ["A1", "A2", "A3"]},
        index=[10, 20, 30],
    )
    risk_scores = pd.Series([0.95, 0.50, 0.85], index=[20, 10, 30])

    alerts = build_alerts(master, risk_scores, threshold=0.7)

    assert len(alerts) == 2
    assert set(alerts.index) == {20, 30}
    assert alerts.loc[20, "Patient_ID"] == "P2"
    assert alerts.loc[20, "risk_score"] == pytest.approx(0.95)
    assert alerts.loc[30, "Patient_ID"] == "P3"
    assert alerts.loc[30, "risk_score"] == pytest.approx(0.85)


def test_build_admission_summary_missing_optional_tables():
    transformer = DataTransformer()
    data = {
        "Admissions": pd.DataFrame({
            "Admission_ID": ["AD1"],
            "Patient_ID": ["PT1"],
            "Admission_Date": ["2024-01-01"],
            "Discharge_Date": ["2024-01-05"],
            "Department": ["Cardiology"],
            "Admission_Type": ["Emergency"],
            "Length_of_Stay": [4],
            "ICU_Required": [0],
            "Readmission_Flag": [0],
        }),
        "Diagnoses": pd.DataFrame({
            "Diagnosis_ID": ["D1"],
            "Admission_ID": ["AD1"],
            "ICD_Code": ["I10"],
            "Diagnosis_Description": ["HTN"],
            "Primary_Diagnosis": [1],
        }),
    }

    summary = transformer.build_admission_summary(data)

    assert len(summary) == 1
    assert summary.iloc[0]["diagnosis_count"] == 1
    assert summary.iloc[0]["medication_count"] == 0
    assert summary.iloc[0]["lab_test_count"] == 0


def test_build_admission_summary_uses_normalized_admission_id():
    transformer = DataTransformer()
    data = {
        "Admissions": pd.DataFrame({
            "Admission_ID": ["AD1", "AD2"],
            "Patient_ID": ["PT1", "PT2"],
            "Admission_Date": ["2024-01-01", "2024-01-02"],
            "Discharge_Date": ["2024-01-05", "2024-01-06"],
            "Department": ["Cardiology", "Neurology"],
            "Admission_Type": ["Emergency", "Elective"],
            "Length_of_Stay": [4, 3],
            "ICU_Required": [0, 1],
            "Readmission_Flag": [0, 1],
        }),
        "Medications": pd.DataFrame({
            "Medication_ID": ["M1", "M2"],
            "Admission_ID": ["AD1", "AD1"],
            "Medication_Name": ["Aspirin", "Metformin"],
            "Dosage": ["100mg", "500mg"],
            "Frequency": ["Daily", "BID"],
            "Prescribed_Date": ["2024-01-01", "2024-01-02"],
        }),
    }

    summary = transformer.build_admission_summary(data)

    assert summary.loc[summary["admission_id"] == "AD1", "medication_count"].iloc[0] == 2
    assert summary.loc[summary["admission_id"] == "AD2", "medication_count"].iloc[0] == 0


def test_csv_loader_parses_only_relevant_date_columns(tmp_path):
    admissions = tmp_path / "admissions.csv"
    admissions.write_text(
        "Admission_ID,Patient_ID,Admission_Date,Discharge_Date,Department,"
        "Admission_Type,Length_of_Stay,ICU_Required,Readmission_Flag\n"
        "AD1,PT1,2024-01-01,2024-01-05,Cardiology,Emergency,4,0,0\n",
        encoding="utf-8",
    )

    ingestor = CSVIngestor(data_dir=tmp_path)
    df = ingestor.load_table("admissions")

    assert pd.api.types.is_datetime64_any_dtype(df["Admission_Date"])
    assert pd.api.types.is_datetime64_any_dtype(df["Discharge_Date"])


def test_readmission_prepare_features_unknown_category():
    from barekat.ml.readmission import ReadmissionPredictor

    predictor = ReadmissionPredictor()
    train_df = pd.DataFrame({
        "age": [50, 60],
        "gender": ["M", "F"],
        "department": ["Cardiology", "Neurology"],
        "bmi": [25.0, 28.0],
        "diabetes": [0, 1],
        "hypertension": [1, 0],
        "length_of_stay": [3, 5],
        "icu_required": [0, 1],
        "diagnosis_count": [1, 2],
        "medication_count": [2, 3],
        "lab_test_count": [4, 5],
        "readmission_flag": [0, 1],
    })
    predictor._prepare_features(train_df, fit=True)

    predict_df = train_df.copy()
    predict_df.loc[0, "department"] = "Unknown_Dept"

    X = predictor._prepare_features(predict_df, fit=False)
    assert len(X) == 2
