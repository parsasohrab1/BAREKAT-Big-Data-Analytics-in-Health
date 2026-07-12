"""Predictive alerts and monitoring page."""

import streamlit as st
import pandas as pd

from dashboards.utils.ml_analytics import build_alerts, train_readmission_model
from dashboards.utils.styles import render_hero


SEVERITY_FA = {
    "critical": "بحرانی",
    "high": "بالا",
    "medium": "متوسط",
    "low": "پایین",
}


def render(data: dict, master: pd.DataFrame, kpis: dict) -> None:
    render_hero(
        "هشدارهای پیش‌بینی‌کننده",
        "پایش بلادرنگ ریسک بستری مجدد و هشدارهای بالینی",
    )

    if master.empty:
        st.info("داده‌ای برای تولید هشدار وجود ندارد.")
        return

    _, _, risk_scores = train_readmission_model(master)
    master_alert = master.copy()
    master_alert["risk_score"] = risk_scores.values
    alerts = build_alerts(master_alert, risk_scores, threshold=0.65)

    c1, c2, c3, c4 = st.columns(4)
    severity_counts = alerts["severity"].value_counts() if not alerts.empty else pd.Series(dtype=int)
    with c1:
        st.metric("کل هشدارها", len(alerts))
    with c2:
        st.metric("بحرانی", int(severity_counts.get("critical", 0)))
    with c3:
        st.metric("بالا", int(severity_counts.get("high", 0)))
    with c4:
        st.metric("متوسط", int(severity_counts.get("medium", 0)))

    if alerts.empty:
        st.success("هشدار فعالی وجود ندارد.")
        return

    severity_filter = st.multiselect(
        "فیلتر شدت",
        options=["critical", "high", "medium", "low"],
        default=["critical", "high", "medium"],
        format_func=lambda x: SEVERITY_FA.get(x, x),
    )
    dept_filter = st.multiselect(
        "فیلتر بخش",
        options=sorted(alerts["Department"].dropna().unique().tolist()),
        default=sorted(alerts["Department"].dropna().unique().tolist()),
    )

    filtered = alerts[
        alerts["severity"].isin(severity_filter) & alerts["Department"].isin(dept_filter)
    ]

    for _, row in filtered.head(25).iterrows():
        severity = row["severity"]
        badge_class = f"badge-{severity}"
        severity_label = SEVERITY_FA.get(severity, severity)
        st.markdown(
            f"""
            <div class="section-card">
                <span class="badge {badge_class}">{severity_label}</span>
                &nbsp; <strong>{row.get('message', '')}</strong><br>
                <small>
                بیمار: {row.get('Patient_ID', '-')} |
                بستری: {row.get('Admission_ID', '-')} |
                بخش: {row.get('Department', '-')} |
                ریسک: {row.get('risk_score', 0):.0%}
                </small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### جدول هشدارها")
    show_cols = [
        c for c in [
            "Patient_ID", "Admission_ID", "Department", "severity",
            "risk_score", "message", "Readmission_Flag",
        ]
        if c in filtered.columns
    ]
    display = filtered[show_cols].copy()
    if "severity" in display.columns:
        display["severity"] = display["severity"].map(SEVERITY_FA)
    st.dataframe(display, use_container_width=True, hide_index=True)

    csv = filtered[show_cols].to_csv(index=False).encode("utf-8-sig")
    st.download_button("دانلود هشدارها (CSV)", csv, "barekat_alerts.csv", "text/csv")
