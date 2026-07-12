"""Readmission prediction model."""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from barekat.config.settings import get_settings


class ReadmissionPredictor:
    """Predict hospital readmission risk using admission features."""

    FEATURE_COLUMNS = [
        "age", "gender", "bmi", "diabetes", "hypertension",
        "length_of_stay", "icu_required", "diagnosis_count",
        "medication_count", "lab_test_count", "department",
    ]

    def __init__(self) -> None:
        self.settings = get_settings()
        self.model = GradientBoostingClassifier(
            n_estimators=100, max_depth=5, random_state=42
        )
        self.label_encoders: dict[str, LabelEncoder] = {}
        self.model_path = Path(self.settings.data_models_path) / "readmission_model.joblib"
        self.model_path.parent.mkdir(parents=True, exist_ok=True)

    def _prepare_features(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        features = df.copy()
        for col in ("diabetes", "hypertension", "icu_required"):
            if col in features.columns:
                features[col] = features[col].astype(int)

        for col in ("gender", "department"):
            if col not in features.columns:
                continue
            if fit:
                self.label_encoders[col] = LabelEncoder()
                features[col] = self.label_encoders[col].fit_transform(features[col].astype(str))
            else:
                le = self.label_encoders.get(col)
                if le:
                    features[col] = le.transform(features[col].astype(str))

        available = [c for c in self.FEATURE_COLUMNS if c in features.columns]
        return features[available]

    def train(self, data: dict[str, pd.DataFrame]) -> dict:
        patients = data["Patients"]
        admissions = data["Admissions"]

        diag_counts = data["Diagnoses"].groupby("Admission_ID").size().reset_index(name="diagnosis_count")
        diag_counts.columns = ["admission_id", "diagnosis_count"]
        med_counts = data["Medications"].groupby("Admission_ID").size().reset_index(name="medication_count")
        med_counts.columns = ["admission_id", "medication_count"]
        lab_counts = data["Lab_Results"].groupby("Admission_ID").size().reset_index(name="lab_test_count")
        lab_counts.columns = ["admission_id", "lab_test_count"]

        df = admissions.merge(patients, on="Patient_ID", how="left")
        df = df.merge(diag_counts, left_on="Admission_ID", right_on="admission_id", how="left")
        df = df.merge(med_counts, left_on="Admission_ID", right_on="admission_id", how="left", suffixes=("", "_med"))
        df = df.merge(lab_counts, left_on="Admission_ID", right_on="admission_id", how="left", suffixes=("", "_lab"))
        df = df.fillna(0)

        df.columns = [c.lower() for c in df.columns]
        X = self._prepare_features(df, fit=True)
        y = df["readmission_flag"].astype(int)

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        self.model.fit(X_train, y_train)

        train_score = self.model.score(X_train, y_train)
        test_score = self.model.score(X_test, y_test)

        joblib.dump({"model": self.model, "encoders": self.label_encoders}, self.model_path)

        return {
            "train_accuracy": round(train_score, 4),
            "test_accuracy": round(test_score, 4),
            "samples": len(df),
            "model_path": str(self.model_path),
        }

    def load(self) -> None:
        if self.model_path.exists():
            saved = joblib.load(self.model_path)
            self.model = saved["model"]
            self.label_encoders = saved["encoders"]

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        X = self._prepare_features(features, fit=False)
        return self.model.predict_proba(X)[:, 1]

    def generate_alerts(self, data: dict[str, pd.DataFrame], threshold: float | None = None) -> pd.DataFrame:
        threshold = threshold or self.settings.ml_readmission_threshold
        self.load()

        patients = data["Patients"]
        admissions = data["Admissions"]
        diag_counts = data["Diagnoses"].groupby("Admission_ID").size().reset_index(name="diagnosis_count")
        diag_counts.columns = ["admission_id", "diagnosis_count"]
        med_counts = data["Medications"].groupby("Admission_ID").size().reset_index(name="medication_count")
        med_counts.columns = ["admission_id", "medication_count"]
        lab_counts = data["Lab_Results"].groupby("Admission_ID").size().reset_index(name="lab_test_count")
        lab_counts.columns = ["admission_id", "lab_test_count"]

        df = admissions.merge(patients, on="Patient_ID", how="left")
        df = df.merge(diag_counts, left_on="Admission_ID", right_on="admission_id", how="left")
        df = df.merge(med_counts, left_on="Admission_ID", right_on="admission_id", how="left", suffixes=("", "_med"))
        df = df.merge(lab_counts, left_on="Admission_ID", right_on="admission_id", how="left", suffixes=("", "_lab"))
        df = df.fillna(0)
        df.columns = [c.lower() for c in df.columns]

        risks = self.predict(df)
        alerts = []
        for idx, risk in enumerate(risks):
            if risk >= threshold:
                severity = "critical" if risk >= 0.9 else "high" if risk >= 0.8 else "medium"
                alerts.append({
                    "patient_id": df.iloc[idx]["patient_id"],
                    "admission_id": df.iloc[idx]["admission_id"],
                    "alert_type": "readmission_risk",
                    "severity": severity,
                    "message": f"High readmission risk detected (score: {risk:.2%})",
                    "risk_score": round(float(risk), 4),
                })
        return pd.DataFrame(alerts)
