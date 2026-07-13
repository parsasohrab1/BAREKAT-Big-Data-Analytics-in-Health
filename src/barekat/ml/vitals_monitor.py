"""Time-series vital signs monitoring and deterioration scoring."""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split

from barekat.ml.features import aggregate_vitals, build_admission_frame, compute_news_score
from barekat.ml.metrics import evaluate_classifier
from barekat.ml.registry import load_active_artifact, register_model


class VitalsMonitor:
    """Real-time deterioration monitoring from vital-sign time series."""

    MODEL_NAME = "vitals_deterioration"
    FEATURE_COLUMNS = [
        "news_score", "vital_reading_count",
        "heart_rate_mean", "heart_rate_max", "heart_rate_std",
        "respiratory_rate_mean", "respiratory_rate_max",
        "systolic_bp_min", "spo2_min", "temperature_c_max", "lactate_max",
    ]

    def __init__(self) -> None:
        self.model = GradientBoostingClassifier(n_estimators=80, max_depth=4, random_state=42)

    def build_feature_frame(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        base = build_admission_frame(data)
        vitals = data.get("Vital_Signs", pd.DataFrame())
        if vitals.empty:
            base["news_score"] = 0.0
            base["vital_reading_count"] = 0
            return base

        vital_agg = aggregate_vitals(vitals)
        df = base.merge(vital_agg, on="admission_id", how="left")
        df["news_score"] = df.apply(compute_news_score, axis=1)
        df = df.fillna(0)
        return df

    def _build_target(self, df: pd.DataFrame) -> pd.Series:
        """Deterioration proxy: ICU, sepsis, mortality, or high NEWS."""
        target = (
            (df.get("icu_required", 0).astype(int) > 0)
            | (df.get("sepsis_flag", 0).astype(int) > 0)
            | (df.get("mortality_flag", 0).astype(int) > 0)
            | (df.get("news_score", 0) >= 7)
        ).astype(int)
        return target

    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        return df[[c for c in self.FEATURE_COLUMNS if c in df.columns]].fillna(0)

    def train(self, data: dict[str, pd.DataFrame]) -> dict:
        df = self.build_feature_frame(data)
        if df.empty or df.get("vital_reading_count", pd.Series([0])).sum() == 0:
            return {"version": None, "skipped": True, "reason": "no vital signs data"}

        y = self._build_target(df)
        X = self._prepare_features(df)
        if y.nunique() < 2:
            return {"version": None, "skipped": True, "reason": "insufficient deterioration events"}

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        self.model.fit(X_train, y_train)
        test_prob = self.model.predict_proba(X_test)[:, 1]
        test_metrics = evaluate_classifier(y_test.values, test_prob)

        registration = register_model(
            model_name=self.MODEL_NAME,
            artifact={"model": self.model, "feature_columns": list(X.columns)},
            metrics={"test": test_metrics, "feature_columns": list(X.columns)},
            calibration=test_metrics.get("calibration"),
            samples=len(df),
        )
        return {
            "version": registration["version"],
            "samples": len(df),
            "test_auc": test_metrics.get("auc"),
            "test_f1": test_metrics.get("f1"),
            "artifact_path": registration["artifact_path"],
        }

    def load(self) -> bool:
        saved = load_active_artifact(self.MODEL_NAME)
        if not saved:
            return False
        self.model = saved["model"]
        return True

    def score_admissions(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        df = self.build_feature_frame(data)
        X = self._prepare_features(df)
        if not self.load():
            df["deterioration_score"] = (df.get("news_score", 0) / 15.0).clip(0, 1)
            return df[["admission_id", "patient_id", "department", "news_score", "deterioration_score"]]

        df["deterioration_score"] = self.model.predict_proba(X)[:, 1]
        return df[["admission_id", "patient_id", "department", "news_score", "deterioration_score"]]

    def monitor_timeseries(self, vitals: pd.DataFrame, admission_id: str, window_hours: int = 6) -> dict:
        """Sliding-window monitoring for a single admission."""
        col_map = {"Admission_ID": "admission_id", "Recorded_At": "recorded_at"}
        v = vitals.rename(columns={k: val for k, val in col_map.items() if k in vitals.columns})
        if v.empty or "admission_id" not in v.columns:
            return {"admission_id": admission_id, "readings": 0, "status": "no_data"}

        subset = v[v["admission_id"] == admission_id].sort_values("recorded_at")
        if subset.empty:
            return {"admission_id": admission_id, "readings": 0, "status": "no_data"}

        agg = aggregate_vitals(subset)
        if agg.empty:
            return {"admission_id": admission_id, "readings": len(subset), "status": "no_data"}

        row = agg.iloc[0]
        news = compute_news_score(row)
        score_row = pd.DataFrame([row])
        score_row["news_score"] = news
        score_row["vital_reading_count"] = len(subset)

        deterioration = float(news / 15.0)
        if self.load():
            X = self._prepare_features(score_row)
            deterioration = float(self.model.predict_proba(X)[0, 1])

        status = "stable"
        if news >= 7 or deterioration >= 0.7:
            status = "critical"
        elif news >= 5 or deterioration >= 0.5:
            status = "warning"

        return {
            "admission_id": admission_id,
            "readings": len(subset),
            "window_hours": window_hours,
            "news_score": round(news, 1),
            "deterioration_score": round(deterioration, 4),
            "status": status,
            "latest_vitals": subset.iloc[-1].to_dict(),
        }

    def generate_alerts(self, data: dict[str, pd.DataFrame], threshold: float = 0.55) -> pd.DataFrame:
        scores = self.score_admissions(data)
        high = scores[scores["deterioration_score"] >= threshold]
        alerts = []
        for _, row in high.iterrows():
            news = float(row.get("news_score", 0))
            det = float(row["deterioration_score"])
            severity = "critical" if det >= 0.8 or news >= 9 else "high" if det >= 0.65 else "medium"
            alerts.append({
                "patient_id": row["patient_id"],
                "admission_id": row["admission_id"],
                "alert_type": "vitals_deterioration",
                "severity": severity,
                "message": f"Vital deterioration score {det:.0%} (NEWS={news:.0f}) — real-time monitoring",
                "risk_score": round(det, 4),
            })
        return pd.DataFrame(alerts)
