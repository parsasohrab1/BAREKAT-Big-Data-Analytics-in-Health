"""Dashboard helpers for SHAP readmission explanations."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def explain_admission_from_master(
    data: dict[str, pd.DataFrame],
    admission_id: str,
) -> dict | None:
    """Get SHAP explanation via ReadmissionExplainer."""
    try:
        from barekat.ml.explainability import ReadmissionExplainer

        # Convert dashboard data keys to training format
        training_data = _to_training_format(data)
        explainer = ReadmissionExplainer()
        return explainer.explain_admission(training_data, admission_id)
    except Exception:
        return None


def _to_training_format(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Map dashboard table keys to ML training format (PascalCase)."""
    aliases = {
        "patients": "Patients",
        "admissions": "Admissions",
        "diagnoses": "Diagnoses",
        "medications": "Medications",
        "lab_results": "Lab_Results",
        "clinical_notes": "Clinical_Notes",
        "vital_signs": "Vital_Signs",
    }
    result: dict[str, pd.DataFrame] = {}
    for key, df in data.items():
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue
        std_key = aliases.get(key.lower(), key)
        result[std_key] = df
    return result


def shap_waterfall_chart(explanation: dict) -> go.Figure:
    """Horizontal bar chart of SHAP contributions."""
    contribs = explanation.get("contributions", [])
    if not contribs:
        return go.Figure()

    labels = [c["label_fa"] for c in contribs[:10]]
    values = [c["shap_value"] for c in contribs[:10]]
    colors = ["#ef4444" if v > 0 else "#10b981" for v in values]

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=[f"{v:+.3f}" for v in values],
        textposition="outside",
    ))
    fig.update_layout(
        title="تأثیر هر عامل بر ریسک بستری مجدد (SHAP)",
        xaxis_title="تأثیر SHAP (مثبت = افزایش ریسک)",
        yaxis=dict(autorange="reversed"),
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def generate_report_html(explanation: dict) -> str:
    from barekat.ml.clinical_report import generate_clinical_report_html
    return generate_clinical_report_html(explanation)
