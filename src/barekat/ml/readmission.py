"""Readmission prediction model with versioning and metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from barekat.config.settings import get_settings
from barekat.ml.metrics import evaluate_classifier
from barekat.ml.registry import load_active_artifact, register_model
from barekat.ml.thresholds import get_threshold


class ReadmissionPredictor:
    """Predict hospital readmission risk using admission features."""

    MODEL_NAME = "readmission"
    FEATURE_COLUMNS = [
        "age", "gender", "bmi", "diabetes", "hypertension",
        "length_of_stay", "icu_required", "diagnosis_count",
        "medication_count", "lab_test_count", "department",
    ]

    def __init__(self) -> None:
        self.settings = get_settings()
        self.model = GradientBoostingClassifier(
            n_estimators=100, max_depth=5, random_state=42,
        )
        self.label_encoders: dict[str, LabelEncoder] = {}
        self.active_version: str | None = None

    def build_feature_frame(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        patients = data.get("Patients", pd.DataFrame())
        admissions = data.get("Admissions", pd.DataFrame())
        if admissions.empty:
            return pd.DataFrame()

        df = (
            admissions.merge(patients, on="Patient_ID", how="left")
            if not patients.empty
            else admissions.copy()
        )

        count_specs = [
            ("Diagnoses", "diagnosis_count"),
            ("Medications", "medication_count"),
            ("Lab_Results", "lab_test_count"),
        ]
        for table_key, count_col in count_specs:
            if table_key in data and not data[table_key].empty:
                counts = data[table_key].groupby("Admission_ID").size().reset_index(name=count_col)
                counts.columns = ["admission_id", count_col]
                df = df.merge(counts, left_on="Admission_ID", right_on="admission_id", how="left")
                df = df.drop(columns=["admission_id"], errors="ignore")
            else:
                df[count_col] = 0

        df = df.fillna(0)
        df.columns = [c.lower() for c in df.columns]
        return df

    def _prepare_features(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        features = df.copy()
        for col in ("diabetes", "hypertension", "icu_required"):
            if col in features.columns:
                features[col] = features[col].astype(int)

        for col in ("gender", "department"):
            if col not in features.columns:
                continue
            values = features[col].astype(str)
            if fit:
                self.label_encoders[col] = LabelEncoder()
                features[col] = self.label_encoders[col].fit_transform(values)
            else:
                le = self.label_encoders.get(col)
                if le is not None:
                    known = set(le.classes_)
                    values = values.apply(lambda x: x if x in known else le.classes_[0])
                    features[col] = le.transform(values)

        return features[[c for c in self.FEATURE_COLUMNS if c in features.columns]]

    def train(self, data: dict[str, pd.DataFrame]) -> dict:
        df = self.build_feature_frame(data)
        X = self._prepare_features(df, fit=True)
        y = df["readmission_flag"].astype(int)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y if y.nunique() > 1 else None,
        )
        self.model.fit(X_train, y_train)

        train_prob = self.model.predict_proba(X_train)[:, 1]
        test_prob = self.model.predict_proba(X_test)[:, 1]

        train_metrics = evaluate_classifier(y_train.values, train_prob, threshold=self.settings.ml_readmission_threshold)
        test_metrics = evaluate_classifier(y_test.values, test_prob, threshold=self.settings.ml_readmission_threshold)

        artifact = {"model": self.model, "encoders": self.label_encoders}
        registration = register_model(
            model_name=self.MODEL_NAME,
            artifact=artifact,
            metrics={
                "train": train_metrics,
                "test": test_metrics,
                "feature_columns": list(X.columns),
            },
            calibration=test_metrics.get("calibration"),
            samples=len(df),
        )
        self.active_version = registration["version"]

        return {
            "version": registration["version"],
            "samples": len(df),
            "train_auc": train_metrics.get("auc"),
            "test_auc": test_metrics.get("auc"),
            "train_f1": train_metrics.get("f1"),
            "test_f1": test_metrics.get("f1"),
            "test_calibration": test_metrics.get("calibration"),
            "artifact_path": registration["artifact_path"],
        }

    def load(self) -> bool:
        saved = load_active_artifact(self.MODEL_NAME)
        if not saved:
            return False
        self.model = saved["model"]
        self.label_encoders = saved.get("encoders", {})
        return True

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        if not self.load():
            raise RuntimeError("No active readmission model found. Run training first.")
        X = self._prepare_features(features, fit=False)
        return self.model.predict_proba(X)[:, 1]

    def generate_alerts(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        self.load()
        df = self.build_feature_frame(data)
        if df.empty:
            return pd.DataFrame()

        risks = self.predict(df)

        alerts = []
        for (_, row), risk in zip(df.iterrows(), risks):
            department = str(row.get("department", ""))
            threshold = get_threshold(department)
            if risk < threshold:
                continue
            severity = "critical" if risk >= 0.9 else "high" if risk >= 0.8 else "medium"
            alerts.append({
                "patient_id": row["patient_id"],
                "admission_id": row["admission_id"],
                "alert_type": "readmission_risk",
                "severity": severity,
                "message": (
                    f"Readmission risk {risk:.0%} exceeds {department} threshold {threshold:.0%}"
                ),
                "risk_score": round(float(risk), 4),
                "department": department,
                "threshold_used": threshold,
            })
        return pd.DataFrame(alerts)
