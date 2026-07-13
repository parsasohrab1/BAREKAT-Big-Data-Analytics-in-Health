"""SHAP-based explainability for readmission predictions."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from barekat.ml.readmission import ReadmissionPredictor
from barekat.ml.thresholds import get_threshold

FEATURE_LABELS_FA: dict[str, str] = {
    "age": "سن",
    "gender": "جنسیت",
    "bmi": "شاخص توده بدنی (BMI)",
    "diabetes": "دیابت",
    "hypertension": "فشار خون بالا",
    "length_of_stay": "مدت بستری (روز)",
    "icu_required": "نیاز به ICU",
    "diagnosis_count": "تعداد تشخیص",
    "medication_count": "تعداد دارو",
    "lab_test_count": "تعداد آزمایش",
    "department": "بخش",
}

FEATURE_LABELS_EN: dict[str, str] = {
    "age": "Age",
    "gender": "Gender",
    "bmi": "BMI",
    "diabetes": "Diabetes",
    "hypertension": "Hypertension",
    "length_of_stay": "Length of stay (days)",
    "icu_required": "ICU required",
    "diagnosis_count": "Diagnosis count",
    "medication_count": "Medication count",
    "lab_test_count": "Lab test count",
    "department": "Department",
}


def _decode_feature_value(feature: str, value: Any, encoders: dict) -> str:
    if feature in ("diabetes", "hypertension", "icu_required"):
        return "بله" if int(value) else "خیر"
    if feature == "gender" and "gender" in encoders:
        le = encoders["gender"]
        try:
            return str(le.inverse_transform([int(value)])[0])
        except Exception:
            return str(value)
    if feature == "department" and "department" in encoders:
        le = encoders["department"]
        try:
            return str(le.inverse_transform([int(value)])[0])
        except Exception:
            return str(value)
    if isinstance(value, float):
        return f"{value:.1f}" if feature in ("bmi", "age") else f"{value:.0f}"
    return str(value)


class ReadmissionExplainer:
    """SHAP explanations for individual readmission risk scores."""

    def __init__(self) -> None:
        self.predictor = ReadmissionPredictor()
        self._explainer = None

    def load(self) -> bool:
        if not self.predictor.load():
            return False
        try:
            import shap
            self._explainer = shap.TreeExplainer(self.predictor.model)
        except Exception:
            self._explainer = None
        return True

    def _resolve_row(self, data: dict[str, pd.DataFrame], admission_id: str) -> tuple[pd.DataFrame, int]:
        df = self.predictor.build_feature_frame(data)
        if df.empty:
            raise ValueError("No admission data available")

        col = "admission_id" if "admission_id" in df.columns else None
        if col is None:
            raise ValueError("admission_id column not found")

        mask = df[col].astype(str) == str(admission_id)
        if not mask.any():
            raise ValueError(f"Admission {admission_id} not found")

        idx = int(df.index[mask][0])
        return df, idx

    def explain_admission(
        self,
        data: dict[str, pd.DataFrame],
        admission_id: str,
    ) -> dict[str, Any]:
        if not self.load():
            raise RuntimeError("No active readmission model. Train first.")

        df, row_idx = self._resolve_row(data, admission_id)
        row = df.loc[row_idx]
        X = self.predictor._prepare_features(df.iloc[[row_idx]], fit=False)
        risk = float(self.predictor.predict(df.iloc[[row_idx]])[0])
        department = str(row.get("department", ""))
        threshold = get_threshold(department)

        contributions = self._compute_contributions(X)
        increasing = [c for c in contributions if c["shap_value"] > 0]
        decreasing = [c for c in contributions if c["shap_value"] < 0]
        increasing.sort(key=lambda x: x["shap_value"], reverse=True)
        decreasing.sort(key=lambda x: x["shap_value"])

        summary_fa = _build_summary_fa(risk, threshold, increasing[:3])

        return {
            "admission_id": str(admission_id),
            "patient_id": str(row.get("patient_id", "")),
            "department": department,
            "risk_score": round(risk, 4),
            "risk_percent": f"{risk:.0%}",
            "threshold": threshold,
            "above_threshold": risk >= threshold,
            "severity": _severity(risk),
            "model_version": self.predictor.active_version,
            "base_value": contributions[0].get("base_value") if contributions else None,
            "contributions": contributions,
            "top_risk_factors": increasing[:5],
            "protective_factors": decreasing[:3],
            "summary_fa": summary_fa,
            "summary_en": _build_summary_en(risk, threshold, increasing[:3]),
            "patient_context": {
                "age": row.get("age"),
                "gender": _decode_feature_value("gender", row.get("gender"), self.predictor.label_encoders),
                "bmi": row.get("bmi"),
                "diabetes": bool(row.get("diabetes")),
                "hypertension": bool(row.get("hypertension")),
                "length_of_stay": row.get("length_of_stay"),
                "icu_required": bool(row.get("icu_required")),
                "diagnosis_count": int(row.get("diagnosis_count", 0)),
                "medication_count": int(row.get("medication_count", 0)),
                "lab_test_count": int(row.get("lab_test_count", 0)),
            },
        }

    def _compute_contributions(self, X: pd.DataFrame) -> list[dict[str, Any]]:
        feature_names = list(X.columns)
        row_values = X.iloc[0]

        if self._explainer is not None:
            shap_values = self._explainer.shap_values(X)
            if isinstance(shap_values, list):
                shap_values = shap_values[1]  # positive class
            base_value = float(self._explainer.expected_value)
            if isinstance(base_value, np.ndarray):
                base_value = float(base_value[1]) if len(base_value) > 1 else float(base_value[0])
            values = shap_values[0]
        else:
            # Fallback: model feature importances scaled by deviation from mean
            base_value = 0.0
            importances = self.predictor.model.feature_importances_
            values = importances * (row_values.values - row_values.mean())

        contributions = []
        for i, feat in enumerate(feature_names):
            raw_val = row_values.iloc[i]
            contributions.append({
                "feature": feat,
                "label_fa": FEATURE_LABELS_FA.get(feat, feat),
                "label_en": FEATURE_LABELS_EN.get(feat, feat),
                "value": _decode_feature_value(feat, raw_val, self.predictor.label_encoders),
                "raw_value": float(raw_val) if pd.notna(raw_val) else None,
                "shap_value": round(float(values[i]), 4),
                "impact": "increases_risk" if float(values[i]) > 0 else "decreases_risk",
                "base_value": round(base_value, 4) if i == 0 else None,
            })
        contributions.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
        return contributions


def _severity(risk: float) -> str:
    if risk >= 0.9:
        return "critical"
    if risk >= 0.8:
        return "high"
    if risk >= 0.7:
        return "medium"
    return "low"


def _build_summary_fa(risk: float, threshold: float, top_factors: list[dict]) -> str:
    if risk >= threshold:
        intro = f"این بیمار با احتمال {risk:.0%} در معرض خطر بستری مجدد است (آستانه بخش: {threshold:.0%})."
    else:
        intro = f"ریسک بستری مجدد {risk:.0%} است — زیر آستانه بخش ({threshold:.0%})."

    if not top_factors:
        return intro

    reasons = "؛ ".join(
        f"{f['label_fa']} ({f['value']})" for f in top_factors[:3] if f["shap_value"] > 0
    )
    if reasons:
        return f"{intro} عوامل اصلی افزایش ریسک: {reasons}."
    return intro


def _build_summary_en(risk: float, threshold: float, top_factors: list[dict]) -> str:
    if risk >= threshold:
        intro = f"This patient has a {risk:.0%} predicted readmission risk (department threshold: {threshold:.0%})."
    else:
        intro = f"Readmission risk is {risk:.0%}, below the department threshold ({threshold:.0%})."
    if not top_factors:
        return intro
    reasons = ", ".join(
        f"{f['label_en']}={f['value']}" for f in top_factors[:3] if f["shap_value"] > 0
    )
    if reasons:
        return f"{intro} Key risk drivers: {reasons}."
    return intro
