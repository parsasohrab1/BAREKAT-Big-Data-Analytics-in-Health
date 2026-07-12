"""Tests for ETL transformers."""

import pandas as pd
from barekat.etl.transformers import DataTransformer


def test_normalize_patients():
    transformer = DataTransformer()
    df = pd.DataFrame({
        "Patient_ID": ["PT00001"],
        "Age": [45],
        "Gender": ["M"],
        "Blood_Type": ["A+"],
        "BMI": [25.0],
        "Smoking_Status": ["Never"],
        "Diabetes": [0],
        "Hypertension": [1],
    })
    result = transformer.clean_patients(df)
    assert "patient_id" in result.columns
    assert result.iloc[0]["patient_id"] == "PT00001"
