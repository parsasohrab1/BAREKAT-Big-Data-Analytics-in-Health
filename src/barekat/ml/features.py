"""Shared feature engineering for ML models."""

from __future__ import annotations

import pandas as pd


def build_admission_frame(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge patients, admissions, and per-admission counts."""
    patients = data["Patients"]
    admissions = data["Admissions"]

    diag_counts = (
        data["Diagnoses"].groupby("Admission_ID").size().reset_index(name="diagnosis_count")
    )
    diag_counts.columns = ["admission_id", "diagnosis_count"]

    med_counts = (
        data["Medications"].groupby("Admission_ID").size().reset_index(name="medication_count")
    )
    med_counts.columns = ["admission_id", "medication_count"]

    lab_df = data.get("Lab_Results", pd.DataFrame())
    if not lab_df.empty:
        lab_counts = lab_df.groupby("Admission_ID").size().reset_index(name="lab_test_count")
        lab_counts.columns = ["admission_id", "lab_test_count"]
        abnormal = (
            lab_df.groupby("Admission_ID")["Abnormal_Flag"].mean().reset_index(name="abnormal_lab_rate")
        )
        abnormal.columns = ["admission_id", "abnormal_lab_rate"]
    else:
        lab_counts = pd.DataFrame(columns=["admission_id", "lab_test_count"])
        abnormal = pd.DataFrame(columns=["admission_id", "abnormal_lab_rate"])

    df = admissions.merge(patients, on="Patient_ID", how="left")
    df = df.merge(diag_counts, left_on="Admission_ID", right_on="admission_id", how="left")
    df = df.merge(med_counts, left_on="Admission_ID", right_on="admission_id", how="left", suffixes=("", "_med"))
    df = df.merge(lab_counts, left_on="Admission_ID", right_on="admission_id", how="left", suffixes=("", "_lab"))
    df = df.merge(abnormal, left_on="Admission_ID", right_on="admission_id", how="left", suffixes=("", "_abn"))
    df = df.fillna(0)
    df.columns = [c.lower() for c in df.columns]
    return df


def aggregate_vitals(vitals: pd.DataFrame) -> pd.DataFrame:
    """Aggregate vital-sign time series per admission."""
    if vitals.empty:
        return pd.DataFrame()

    col_map = {
        "Admission_ID": "admission_id",
        "Heart_Rate": "heart_rate",
        "Respiratory_Rate": "respiratory_rate",
        "Systolic_BP": "systolic_bp",
        "Diastolic_BP": "diastolic_bp",
        "Temperature_C": "temperature_c",
        "SpO2": "spo2",
        "Lactate": "lactate",
    }
    v = vitals.rename(columns={k: val for k, val in col_map.items() if k in vitals.columns})
    if "admission_id" not in v.columns:
        return pd.DataFrame()

    numeric_cols = ["heart_rate", "respiratory_rate", "systolic_bp", "diastolic_bp", "temperature_c", "spo2", "lactate"]
    for col in numeric_cols:
        if col in v.columns:
            v[col] = pd.to_numeric(v[col], errors="coerce")

    rows = []
    for adm_id, group in v.groupby("admission_id"):
        row: dict = {"admission_id": adm_id, "vital_reading_count": len(group)}
        for col in numeric_cols:
            if col not in group.columns:
                continue
            series = group[col].dropna()
            if series.empty:
                continue
            row[f"{col}_mean"] = float(series.mean())
            row[f"{col}_std"] = float(series.std()) if len(series) > 1 else 0.0
            row[f"{col}_min"] = float(series.min())
            row[f"{col}_max"] = float(series.max())
        rows.append(row)
    return pd.DataFrame(rows)


def compute_news_score(row: pd.Series) -> float:
    """National Early Warning Score (simplified) from vital aggregates."""
    score = 0.0
    hr = row.get("heart_rate_mean", row.get("heart_rate", 80))
    rr = row.get("respiratory_rate_mean", row.get("respiratory_rate", 16))
    temp = row.get("temperature_c_mean", row.get("temperature_c", 37))
    sbp = row.get("systolic_bp_mean", row.get("systolic_bp", 120))
    spo2 = row.get("spo2_mean", row.get("spo2", 98))

    if hr <= 40 or hr >= 131:
        score += 3
    elif hr <= 50 or hr >= 111:
        score += 2
    elif hr <= 60 or hr >= 101:
        score += 1

    if rr <= 8 or rr >= 25:
        score += 3
    elif rr >= 21:
        score += 2
    elif rr >= 19:
        score += 1

    if temp <= 35.0:
        score += 3
    elif temp >= 39.1:
        score += 2
    elif temp >= 38.1:
        score += 1

    if sbp <= 90 or sbp >= 220:
        score += 3
    elif sbp <= 100:
        score += 2
    elif sbp <= 110:
        score += 1

    if spo2 <= 91:
        score += 3
    elif spo2 <= 93:
        score += 2
    elif spo2 <= 95:
        score += 1

    return score
