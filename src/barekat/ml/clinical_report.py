"""Printable clinical report for readmission risk explanations."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any


def generate_clinical_report_html(explanation: dict[str, Any], *, model_version: str | None = None) -> str:
    """Generate a print-friendly HTML report for the clinical team."""
    ctx = explanation.get("patient_context", {})
    top_risk = explanation.get("top_risk_factors", [])
    protective = explanation.get("protective_factors", [])
    version = model_version or explanation.get("model_version") or "—"
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    risk_pct = explanation.get("risk_percent", "—")
    severity = explanation.get("severity", "low")
    severity_fa = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"}.get(severity, severity)

    risk_rows = "".join(
        _factor_row(f["label_fa"], f["value"], f["shap_value"], positive=True)
        for f in top_risk
    )
    protect_rows = "".join(
        _factor_row(f["label_fa"], f["value"], f["shap_value"], positive=False)
        for f in protective
    )

    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8"/>
  <title>Readmission Risk Report — {escape(str(explanation.get('admission_id', '')))}</title>
  <style>
    @media print {{
      .no-print {{ display: none; }}
      body {{ margin: 0; }}
    }}
    body {{
      font-family: Tahoma, 'Segoe UI', Arial, sans-serif;
      max-width: 800px;
      margin: 2rem auto;
      color: #1e293b;
      line-height: 1.6;
    }}
    h1 {{ color: #0891B2; font-size: 1.4rem; border-bottom: 2px solid #0891B2; padding-bottom: 0.5rem; }}
    h2 {{ color: #0f766e; font-size: 1.1rem; margin-top: 1.5rem; }}
    .risk-box {{
      background: #fef2f2;
      border: 2px solid #ef4444;
      border-radius: 8px;
      padding: 1rem;
      margin: 1rem 0;
      text-align: center;
    }}
    .risk-score {{ font-size: 2.5rem; font-weight: bold; color: #dc2626; }}
    table {{ width: 100%; border-collapse: collapse; margin: 0.5rem 0; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 0.5rem 0.75rem; text-align: right; }}
    th {{ background: #f1f5f9; }}
    .positive {{ color: #dc2626; }}
    .negative {{ color: #059669; }}
    .disclaimer {{
      font-size: 0.85rem;
      color: #64748b;
      border-top: 1px solid #e2e8f0;
      margin-top: 2rem;
      padding-top: 1rem;
    }}
    .meta {{ font-size: 0.85rem; color: #64748b; }}
    .summary {{ background: #f0fdfa; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
    .context-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; }}
    .context-item {{ background: #f8fafc; padding: 0.5rem; border-radius: 4px; }}
  </style>
</head>
<body>
  <button class="no-print" onclick="window.print()" style="padding:0.5rem 1rem;cursor:pointer;">
    🖨️ Print report
  </button>

  <h1>BAREKAT — Readmission Risk Report</h1>
  <p class="meta">Admission ID: <strong>{escape(str(explanation.get('admission_id', '')))}</strong>
     | Patient: <strong>{escape(str(explanation.get('patient_id', '')))}</strong>
     | Department: <strong>{escape(str(explanation.get('department', '')))}</strong></p>

  <div class="risk-box">
    <div>Readmission probability (30 days)</div>
    <div class="risk-score">{escape(str(risk_pct))}</div>
    <div>Risk level: <strong>{severity_fa}</strong>
      | Department threshold: {explanation.get('threshold', 0):.0%}</div>
  </div>

  <div class="summary">
    <strong>Clinical summary:</strong><br/>
    {escape(explanation.get('summary_fa', ''))}
  </div>

  <h2>Patient profile</h2>
  <div class="context-grid">
    <div class="context-item">Age: {ctx.get('age', '—')}</div>
    <div class="context-item">Gender: {escape(str(ctx.get('gender', '—')))}</div>
    <div class="context-item">BMI: {ctx.get('bmi', '—')}</div>
    <div class="context-item">Length of stay: {ctx.get('length_of_stay', '—')} days</div>
    <div class="context-item">Diabetes: {'Yes' if ctx.get('diabetes') else 'No'}</div>
    <div class="context-item">Hypertension: {'Yes' if ctx.get('hypertension') else 'No'}</div>
    <div class="context-item">ICU: {'Yes' if ctx.get('icu_required') else 'No'}</div>
    <div class="context-item">Diagnoses / medications / tests: {ctx.get('diagnosis_count', 0)} / {ctx.get('medication_count', 0)} / {ctx.get('lab_test_count', 0)}</div>
  </div>

  <h2>Why is this patient high-risk? (SHAP)</h2>
  <p>Factors that contributed most to the increase in risk:</p>
  <table>
    <thead><tr><th>Factor</th><th>Value</th><th>Effect on risk</th></tr></thead>
    <tbody>{risk_rows or '<tr><td colspan="3">—</td></tr>'}</tbody>
  </table>

  {"<h2>Protective factors</h2><table><thead><tr><th>Factor</th><th>Value</th><th>Effect</th></tr></thead><tbody>" + protect_rows + "</tbody></table>" if protect_rows else ""}

  <div class="disclaimer">
    <strong>Disclaimer:</strong> This report was generated by a clinical decision support (CDS) system and
    does not replace medical judgment. The final decision rests with the treatment team.
    <br/>Model: readmission v{escape(str(version))} | Generated: {generated_at}
    <br/>Explanation method: SHAP (SHapley Additive exPlanations)
  </div>
</body>
</html>"""


def _factor_row(label: str, value: str, shap_val: float, *, positive: bool) -> str:
    css = "positive" if positive else "negative"
    sign = "+" if shap_val > 0 else ""
    return (
        f"<tr><td>{escape(label)}</td>"
        f"<td>{escape(str(value))}</td>"
        f'<td class="{css}">{sign}{shap_val:.3f}</td></tr>'
    )
