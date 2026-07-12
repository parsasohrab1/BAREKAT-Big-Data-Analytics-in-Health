"""ML analytics helpers for dashboard visualizations."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler


def _encode_features(df: pd.DataFrame, encoders: dict | None = None, fit: bool = False) -> tuple[pd.DataFrame, dict]:
    encoders = encoders or {}
    result = df.copy()

    for col in ("diabetes", "hypertension", "icu_required"):
        if col in result.columns:
            result[col] = result[col].astype(int)

    for col in ("gender", "department"):
        if col not in result.columns:
            continue
        if fit:
            encoders[col] = LabelEncoder()
            result[col] = encoders[col].fit_transform(result[col].astype(str))
        else:
            le = encoders.get(col)
            if le is not None:
                known = set(le.classes_)
                result[col] = result[col].astype(str).apply(lambda x: x if x in known else le.classes_[0])
                result[col] = le.transform(result[col])

    return result, encoders


def build_readmission_features(master: pd.DataFrame) -> pd.DataFrame:
    df = master.copy()
    df.columns = [c.lower() for c in df.columns]
    return df


def train_readmission_model(master: pd.DataFrame) -> tuple[GradientBoostingClassifier, dict, pd.Series]:
    df = build_readmission_features(master)
    if df.empty or "readmission_flag" not in df.columns:
        return GradientBoostingClassifier(), {}, pd.Series(dtype=float)

    feature_cols = [
        c for c in [
            "age", "gender", "bmi", "diabetes", "hypertension",
            "length_of_stay", "icu_required", "diagnosis_count",
            "medication_count", "lab_test_count", "department",
        ]
        if c in df.columns
    ]

    X, encoders = _encode_features(df[feature_cols], fit=True)
    y = df["readmission_flag"].astype(int)

    if y.nunique() < 2:
        probs = pd.Series(np.full(len(df), y.mean()), index=df.index)
        return GradientBoostingClassifier(), encoders, probs

    model = GradientBoostingClassifier(n_estimators=80, max_depth=4, random_state=42)
    model.fit(X, y)
    probs = pd.Series(model.predict_proba(X)[:, 1], index=df.index)
    return model, encoders, probs


def predict_readmission_risk(master: pd.DataFrame, model, encoders: dict) -> pd.Series:
    df = build_readmission_features(master)
    feature_cols = [
        c for c in [
            "age", "gender", "bmi", "diabetes", "hypertension",
            "length_of_stay", "icu_required", "diagnosis_count",
            "medication_count", "lab_test_count", "department",
        ]
        if c in df.columns
    ]
    X, _ = _encode_features(df[feature_cols], encoders=encoders, fit=False)
    return pd.Series(model.predict_proba(X)[:, 1], index=df.index)


def cluster_patients(data: dict[str, pd.DataFrame], n_clusters: int = 5) -> pd.DataFrame:
    patients = data.get("patients", pd.DataFrame()).copy()
    admissions = data.get("admissions", pd.DataFrame())
    if patients.empty:
        return pd.DataFrame()

    if not admissions.empty:
        stats = admissions.groupby("Patient_ID").agg(
            total_admissions=("Admission_ID", "count"),
            avg_los=("Length_of_Stay", "mean"),
            icu_rate=("ICU_Required", "mean"),
            readmission_rate=("Readmission_Flag", "mean"),
        ).reset_index()
        features = patients.merge(stats, on="Patient_ID", how="left").fillna(0)
    else:
        features = patients.copy()

    features.columns = [c.lower() for c in features.columns]
    numeric_cols = [
        c for c in [
            "age", "bmi", "diabetes", "hypertension",
            "total_admissions", "avg_los", "icu_rate", "readmission_rate",
        ]
        if c in features.columns
    ]
    if "gender" in features.columns:
        features["gender_m"] = (features["gender"] == "M").astype(int)
        numeric_cols.append("gender_m")

    if not numeric_cols:
        return pd.DataFrame()

    X = StandardScaler().fit_transform(features[numeric_cols])
    n_clusters = min(n_clusters, len(features))
    labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit_predict(X)
    features["cluster"] = labels
    return features[["patient_id", "cluster"] + numeric_cols]


def build_alerts(master: pd.DataFrame, risk_scores: pd.Series, threshold: float = 0.65) -> pd.DataFrame:
    if master.empty or risk_scores.empty:
        return pd.DataFrame()

    alerts = master.copy()
    alerts["risk_score"] = risk_scores.values
    alerts = alerts[alerts["risk_score"] >= threshold].copy()

    def severity(score: float) -> str:
        if score >= 0.9:
            return "critical"
        if score >= 0.8:
            return "high"
        if score >= 0.7:
            return "medium"
        return "low"

    alerts["severity"] = alerts["risk_score"].apply(severity)
    alerts["alert_type"] = "readmission_risk"
    alerts["message"] = alerts["risk_score"].apply(lambda s: f"احتمال بستری مجدد: {s:.0%}")
    return alerts.sort_values("risk_score", ascending=False)
