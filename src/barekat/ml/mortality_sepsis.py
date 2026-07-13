"""Mortality and sepsis early-warning models."""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from barekat.config.settings import get_settings
from barekat.ml.features import aggregate_vitals, build_admission_frame, compute_news_score
from barekat.ml.metrics import evaluate_classifier
from barekat.ml.registry import load_active_artifact, register_model


class EarlyWarningPredictor:
    """Early warning for in-hospital mortality and sepsis."""

    MODEL_MORTALITY = "mortality"
    MODEL_SEPSIS = "sepsis"
    FEATURE_COLUMNS = [
        "age", "gender", "bmi", "diabetes", "hypertension", "icu_required",
        "admission_type", "department", "diagnosis_count", "medication_count",
        "lab_test_count", "abnormal_lab_rate", "news_score",
    ]

    def __init__(self) -> None:
        self.settings = get_settings()
        self.mortality_model = GradientBoostingClassifier(n_estimators=80, max_depth=4, random_state=42)
        self.sepsis_model = GradientBoostingClassifier(n_estimators=80, max_depth=4, random_state=42)
        self.label_encoders: dict[str, LabelEncoder] = {}

    def build_feature_frame(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        df = build_admission_frame(data)
        vitals = data.get("Vital_Signs", pd.DataFrame())
        if not vitals.empty:
            vital_agg = aggregate_vitals(vitals)
            df = df.merge(vital_agg, on="admission_id", how="left")
            df["news_score"] = df.apply(compute_news_score, axis=1)
        else:
            df["news_score"] = 0.0
        df = df.fillna(0)
        return df

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

    def _train_binary(self, X, y, model, model_name: str) -> dict:
        if y.nunique() < 2:
            return {"version": None, "skipped": True, "reason": "insufficient class diversity"}

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y,
        )
        model.fit(X_train, y_train)
        train_prob = model.predict_proba(X_train)[:, 1]
        test_prob = model.predict_proba(X_test)[:, 1]
        train_metrics = evaluate_classifier(y_train.values, train_prob)
        test_metrics = evaluate_classifier(y_test.values, test_prob)

        registration = register_model(
            model_name=model_name,
            artifact={"model": model, "encoders": self.label_encoders},
            metrics={"train": train_metrics, "test": test_metrics, "feature_columns": list(X.columns)},
            calibration=test_metrics.get("calibration"),
            samples=len(y),
        )
        return {
            "version": registration["version"],
            "test_auc": test_metrics.get("auc"),
            "test_f1": test_metrics.get("f1"),
            "artifact_path": registration["artifact_path"],
        }

    def train(self, data: dict[str, pd.DataFrame]) -> dict:
        df = self.build_feature_frame(data)
        X = self._prepare_features(df, fit=True)

        mortality_col = "mortality_flag" if "mortality_flag" in df.columns else None
        sepsis_col = "sepsis_flag" if "sepsis_flag" in df.columns else None

        results: dict = {}
        if mortality_col:
            results["mortality"] = self._train_binary(
                X, df[mortality_col].astype(int), self.mortality_model, self.MODEL_MORTALITY,
            )
        if sepsis_col:
            results["sepsis"] = self._train_binary(
                X, df[sepsis_col].astype(int), self.sepsis_model, self.MODEL_SEPSIS,
            )
        return results

    def _load_model(self, model_name: str):
        saved = load_active_artifact(model_name)
        if not saved:
            return None
        self.label_encoders = saved.get("encoders", self.label_encoders)
        return saved["model"]

    def predict_risks(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        df = self.build_feature_frame(data)
        X = self._prepare_features(df, fit=False)
        out = df[["admission_id", "patient_id", "department"]].copy()

        mortality_model = self._load_model(self.MODEL_MORTALITY)
        if mortality_model is not None:
            out["mortality_risk"] = mortality_model.predict_proba(X)[:, 1]
        else:
            out["mortality_risk"] = 0.0

        sepsis_model = self._load_model(self.MODEL_SEPSIS)
        if sepsis_model is not None:
            out["sepsis_risk"] = sepsis_model.predict_proba(X)[:, 1]
        else:
            out["sepsis_risk"] = 0.0

        return out

    def generate_alerts(self, data: dict[str, pd.DataFrame], threshold: float = 0.6) -> pd.DataFrame:
        risks = self.predict_risks(data)
        alerts = []
        for _, row in risks.iterrows():
            for alert_type, risk_col in (("mortality_risk", "mortality_risk"), ("sepsis_risk", "sepsis_risk")):
                risk = float(row[risk_col])
                if risk < threshold:
                    continue
                severity = "critical" if risk >= 0.85 else "high" if risk >= 0.7 else "medium"
                label = "Mortality" if alert_type == "mortality_risk" else "Sepsis"
                alerts.append({
                    "patient_id": row["patient_id"],
                    "admission_id": row["admission_id"],
                    "alert_type": alert_type,
                    "severity": severity,
                    "message": f"{label} early warning: risk {risk:.0%} (NEWS-based features)",
                    "risk_score": round(risk, 4),
                })
        return pd.DataFrame(alerts)
