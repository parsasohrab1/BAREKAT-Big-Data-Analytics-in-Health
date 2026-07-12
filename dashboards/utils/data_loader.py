"""Shared data loading and preprocessing for the dashboard."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

DATA_DIR = Path(os.getenv("DATA_DIR", "./data/raw"))
MODELS_DIR = Path(os.getenv("MODELS_DIR", "./data/models"))

FILE_MAP = {
    "patients": "patients.csv",
    "admissions": "admissions.csv",
    "diagnoses": "diagnoses.csv",
    "medications": "medications.csv",
    "lab_results": "lab_results.csv",
}

DATE_COLUMNS = {
    "admissions": ["Admission_Date", "Discharge_Date"],
    "medications": ["Prescribed_Date"],
    "lab_results": ["Test_Date"],
}


def load_raw_tables(data_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    base = data_dir or DATA_DIR
    tables: dict[str, pd.DataFrame] = {}
    for name, filename in FILE_MAP.items():
        path = base / filename
        if not path.exists():
            continue
        parse_dates = DATE_COLUMNS.get(name)
        tables[name] = pd.read_csv(path, parse_dates=parse_dates)
    return tables


def build_master_admissions(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if "admissions" not in data or "patients" not in data:
        return pd.DataFrame()

    admissions = data["admissions"].copy()
    patients = data["patients"].copy()

    diag_counts = (
        data.get("diagnoses", pd.DataFrame())
        .groupby("Admission_ID")
        .size()
        .reset_index(name="diagnosis_count")
    )
    med_counts = (
        data.get("medications", pd.DataFrame())
        .groupby("Admission_ID")
        .size()
        .reset_index(name="medication_count")
    )
    lab_counts = (
        data.get("lab_results", pd.DataFrame())
        .groupby("Admission_ID")
        .size()
        .reset_index(name="lab_test_count")
    )

    master = admissions.merge(patients, on="Patient_ID", how="left")
    master = master.merge(diag_counts, on="Admission_ID", how="left")
    master = master.merge(med_counts, on="Admission_ID", how="left")
    master = master.merge(lab_counts, on="Admission_ID", how="left")
    master[["diagnosis_count", "medication_count", "lab_test_count"]] = master[
        ["diagnosis_count", "medication_count", "lab_test_count"]
    ].fillna(0)

    if "Admission_Date" in master.columns:
        master["admission_month"] = pd.to_datetime(master["Admission_Date"]).dt.to_period("M").astype(str)

    return master


def compute_kpis(data: dict[str, pd.DataFrame]) -> dict:
    patients = data.get("patients", pd.DataFrame())
    admissions = data.get("admissions", pd.DataFrame())
    diagnoses = data.get("diagnoses", pd.DataFrame())
    medications = data.get("medications", pd.DataFrame())
    lab_results = data.get("lab_results", pd.DataFrame())

    readmit_rate = 0.0
    avg_los = 0.0
    icu_rate = 0.0
    abnormal_rate = 0.0

    if not admissions.empty:
        readmit_rate = admissions["Readmission_Flag"].mean() * 100
        avg_los = admissions["Length_of_Stay"].mean()
        icu_rate = admissions["ICU_Required"].mean() * 100

    if not lab_results.empty:
        abnormal_rate = lab_results["Abnormal_Flag"].mean() * 100

    return {
        "patients": len(patients),
        "admissions": len(admissions),
        "diagnoses": len(diagnoses),
        "medications": len(medications),
        "lab_results": len(lab_results),
        "readmit_rate": readmit_rate,
        "avg_los": avg_los,
        "icu_rate": icu_rate,
        "abnormal_rate": abnormal_rate,
        "departments": admissions["Department"].nunique() if not admissions.empty else 0,
    }


def apply_filters(
    master: pd.DataFrame,
    departments: list[str] | None = None,
    genders: list[str] | None = None,
    admission_types: list[str] | None = None,
) -> pd.DataFrame:
    filtered = master.copy()
    if departments and "Department" in filtered.columns:
        filtered = filtered[filtered["Department"].isin(departments)]
    if genders and "Gender" in filtered.columns:
        filtered = filtered[filtered["Gender"].isin(genders)]
    if admission_types and "Admission_Type" in filtered.columns:
        filtered = filtered[filtered["Admission_Type"].isin(admission_types)]
    return filtered
