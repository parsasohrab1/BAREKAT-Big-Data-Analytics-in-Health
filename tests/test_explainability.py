"""Tests for SHAP readmission explainability."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from barekat.ml.clinical_report import generate_clinical_report_html
from barekat.ml.explainability import ReadmissionExplainer, _build_summary_fa


def _sample_data(n: int = 40) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(42)
    patients = pd.DataFrame({
        "Patient_ID": [f"PT{i:05d}" for i in range(n)],
        "Age": rng.integers(30, 85, n),
        "Gender": rng.choice(["M", "F"], n),
        "BMI": rng.uniform(20, 35, n).round(1),
        "Diabetes": rng.choice([True, False], n),
        "Hypertension": rng.choice([True, False], n),
    })
    admissions = pd.DataFrame({
        "Admission_ID": [f"ADM{i:05d}" for i in range(n)],
        "Patient_ID": [f"PT{i:05d}" for i in range(n)],
        "Department": rng.choice(["Cardiology", "Surgery"], n),
        "Length_of_Stay": rng.integers(2, 14, n),
        "ICU_Required": rng.choice([True, False], n),
        "Readmission_Flag": rng.choice([0, 1], n, p=[0.7, 0.3]),
    })
    diagnoses = pd.DataFrame({
        "Admission_ID": np.repeat(admissions["Admission_ID"], 2),
        "ICD_Code": ["I10", "E11"] * n,
    })
    medications = pd.DataFrame({
        "Admission_ID": np.repeat(admissions["Admission_ID"], 3),
        "Medication_Name": ["Aspirin"] * (n * 3),
    })
    labs = pd.DataFrame({
        "Admission_ID": np.repeat(admissions["Admission_ID"], 2),
        "Test_Name": ["CBC"] * (n * 2),
    })
    return {
        "Patients": patients,
        "Admissions": admissions,
        "Diagnoses": diagnoses,
        "Medications": medications,
        "Lab_Results": labs,
    }


def test_explain_admission_after_training():
    shap = pytest.importorskip("shap")
    from barekat.ml.readmission import ReadmissionPredictor

    data = _sample_data()
    predictor = ReadmissionPredictor()
    df = predictor.build_feature_frame(data)
    X = predictor._prepare_features(df, fit=True)
    y = df["readmission_flag"].astype(int)
    predictor.model.fit(X, y)

    explainer = ReadmissionExplainer()
    explainer.predictor = predictor
    explainer._explainer = shap.TreeExplainer(predictor.model)

    result = explainer.explain_admission(data, "ADM00001")
    assert result["admission_id"] == "ADM00001"
    assert 0 <= result["risk_score"] <= 1
    assert len(result["contributions"]) > 0
    assert result["summary_fa"]


def test_clinical_report_html():
    explanation = {
        "admission_id": "ADM00001",
        "patient_id": "PT00001",
        "department": "Cardiology",
        "risk_percent": "72%",
        "risk_score": 0.72,
        "threshold": 0.7,
        "severity": "medium",
        "summary_fa": "ریسک بالا به دلیل سن و تعداد دارو.",
        "top_risk_factors": [
            {"label_fa": "سن", "value": "75", "shap_value": 0.12},
        ],
        "protective_factors": [],
        "patient_context": {
            "age": 75, "gender": "M", "bmi": 28.5,
            "diabetes": True, "hypertension": True,
            "length_of_stay": 7, "icu_required": False,
            "diagnosis_count": 2, "medication_count": 5, "lab_test_count": 3,
        },
    }
    html = generate_clinical_report_html(explanation)
    assert "ADM00001" in html
    assert "SHAP" in html
    assert "چاپ گزارش" in html


def test_summary_fa():
    factors = [{"label_fa": "سن", "value": "80", "shap_value": 0.1}]
    text = _build_summary_fa(0.75, 0.7, factors)
    assert "75%" in text
    assert "سن" in text
