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
    severity_fa = {"critical": "بحرانی", "high": "بالا", "medium": "متوسط", "low": "پایین"}.get(severity, severity)

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
  <title>گزارش ریسک بستری مجدد — {escape(str(explanation.get('admission_id', '')))}</title>
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
    🖨️ چاپ گزارش
  </button>

  <h1>BAREKAT — گزارش ریسک بستری مجدد</h1>
  <p class="meta">شناسه بستری: <strong>{escape(str(explanation.get('admission_id', '')))}</strong>
     | بیمار: <strong>{escape(str(explanation.get('patient_id', '')))}</strong>
     | بخش: <strong>{escape(str(explanation.get('department', '')))}</strong></p>

  <div class="risk-box">
    <div>احتمال بستری مجدد (۳۰ روز)</div>
    <div class="risk-score">{escape(str(risk_pct))}</div>
    <div>سطح خطر: <strong>{severity_fa}</strong>
      | آستانه بخش: {explanation.get('threshold', 0):.0%}</div>
  </div>

  <div class="summary">
    <strong>خلاصه بالینی:</strong><br/>
    {escape(explanation.get('summary_fa', ''))}
  </div>

  <h2>پروفایل بیمار</h2>
  <div class="context-grid">
    <div class="context-item">سن: {ctx.get('age', '—')}</div>
    <div class="context-item">جنسیت: {escape(str(ctx.get('gender', '—')))}</div>
    <div class="context-item">BMI: {ctx.get('bmi', '—')}</div>
    <div class="context-item">مدت بستری: {ctx.get('length_of_stay', '—')} روز</div>
    <div class="context-item">دیابت: {'بله' if ctx.get('diabetes') else 'خیر'}</div>
    <div class="context-item">فشار خون: {'بله' if ctx.get('hypertension') else 'خیر'}</div>
    <div class="context-item">ICU: {'بله' if ctx.get('icu_required') else 'خیر'}</div>
    <div class="context-item">تشخیص / دارو / آزمایش: {ctx.get('diagnosis_count', 0)} / {ctx.get('medication_count', 0)} / {ctx.get('lab_test_count', 0)}</div>
  </div>

  <h2>چرا این بیمار پرخطر است؟ (SHAP)</h2>
  <p>عواملی که بیشترین تأثیر را در افزایش ریسک داشته‌اند:</p>
  <table>
    <thead><tr><th>عامل</th><th>مقدار</th><th>تأثیر بر ریسک</th></tr></thead>
    <tbody>{risk_rows or '<tr><td colspan="3">—</td></tr>'}</tbody>
  </table>

  {"<h2>عوامل محافظتی</h2><table><thead><tr><th>عامل</th><th>مقدار</th><th>تأثیر</th></tr></thead><tbody>" + protect_rows + "</tbody></table>" if protect_rows else ""}

  <div class="disclaimer">
    <strong>سلب مسئولیت:</strong> این گزارش توسط سیستم پشتیبان تصمیم بالینی (CDS) تولید شده و
    جایگزین قضاوت پزشکی نیست. تصمیم نهایی با تیم درمان است.
    <br/>مدل: readmission v{escape(str(version))} | تولید: {generated_at}
    <br/>روش توضیح: SHAP (SHapley Additive exPlanations)
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
