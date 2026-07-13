"""Length of Stay (LOS) prediction for bed planning."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from barekat.ml.features import build_admission_frame
from barekat.ml.metrics import evaluate_regressor
from barekat.ml.registry import load_active_artifact, register_model


class LOSPredictor:
    """Predict expected length of stay at admission time (bed planning)."""

    MODEL_NAME = "los"
    FEATURE_COLUMNS = [
        "age", "gender", "bmi", "diabetes", "hypertension",
        "icu_required", "admission_type", "department",
        "diagnosis_count", "medication_count", "lab_test_count", "abnormal_lab_rate",
    ]

    def __init__(self) -> None:
        self.model = GradientBoostingRegressor(n_estimators=100, max_depth=4, random_state=42)
        self.label_encoders: dict[str, LabelEncoder] = {}

    def build_feature_frame(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        return build_admission_frame(data)

    def _prepare_features(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        features = df.copy()
        for col in ("diabetes", "hypertension", "icu_required"):
            if col in features.columns:
                features[col] = features[col].astype(int)

        for col in ("gender", "department", "admission_type"):
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
        y = df["length_of_stay"].astype(float)
        X = self._prepare_features(df, fit=True)

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)

        train_pred = self.model.predict(X_train)
        test_pred = self.model.predict(X_test)
        train_metrics = evaluate_regressor(y_train.values, train_pred)
        test_metrics = evaluate_regressor(y_test.values, test_pred)

        registration = register_model(
            model_name=self.MODEL_NAME,
            artifact={"model": self.model, "encoders": self.label_encoders},
            metrics={"train": train_metrics, "test": test_metrics, "feature_columns": list(X.columns)},
            samples=len(df),
        )
        return {
            "version": registration["version"],
            "samples": len(df),
            "test_mae": test_metrics.get("mae"),
            "test_rmse": test_metrics.get("rmse"),
            "test_r2": test_metrics.get("r2"),
            "artifact_path": registration["artifact_path"],
        }

    def load(self) -> bool:
        saved = load_active_artifact(self.MODEL_NAME)
        if not saved:
            return False
        self.model = saved["model"]
        self.label_encoders = saved.get("encoders", {})
        return True

    def predict(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        if not self.load():
            raise RuntimeError("No active LOS model found. Run training first.")
        df = self.build_feature_frame(data)
        X = self._prepare_features(df, fit=False)
        preds = self.model.predict(X)
        return pd.DataFrame({
            "admission_id": df["admission_id"].values,
            "patient_id": df["patient_id"].values,
            "department": df.get("department", ""),
            "predicted_los": np.round(preds, 1),
            "actual_los": df["length_of_stay"].values,
        })

    def generate_bed_plan_alerts(self, data: dict[str, pd.DataFrame], los_threshold: float = 10.0) -> pd.DataFrame:
        preds = self.predict(data)
        high = preds[preds["predicted_los"] >= los_threshold].copy()
        if high.empty:
            return pd.DataFrame()

        alerts = []
        for _, row in high.iterrows():
            severity = "critical" if row["predicted_los"] >= 20 else "high" if row["predicted_los"] >= 14 else "medium"
            alerts.append({
                "patient_id": row["patient_id"],
                "admission_id": row["admission_id"],
                "alert_type": "los_planning",
                "severity": severity,
                "message": f"Predicted LOS {row['predicted_los']:.0f} days — bed planning required ({row['department']})",
                "risk_score": round(min(float(row["predicted_los"]) / 30.0, 1.0), 4),
            })
        return pd.DataFrame(alerts)
