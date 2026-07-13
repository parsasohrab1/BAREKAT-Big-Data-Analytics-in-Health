"""Predictive alerts and monitoring page."""

import streamlit as st
import pandas as pd

from dashboards.utils.auth import get_current_user, has_permission
from dashboards.utils.data_loader import get_active_data_source
from dashboards.utils.styles import render_hero

SEVERITY_FA = {
    "critical": "بحرانی",
    "high": "بالا",
    "medium": "متوسط",
    "low": "پایین",
}


def _load_db_alerts() -> pd.DataFrame:
    from barekat.services.alerts import load_active_alerts

    return load_active_alerts()


def _acknowledge(alert_id: int) -> bool:
    from barekat.services.alerts import acknowledge_alert

    return acknowledge_alert(alert_id)


def render(data: dict, master: pd.DataFrame, kpis: dict) -> None:
    render_hero(
        "هشدارهای پیش‌بینی‌کننده",
        "هشدارهای واقعی از analytics.predictive_alerts پس از اجرای ML pipeline",
    )

    user = get_current_user() or {}
    role = user.get("role", "viewer")
    can_ack = has_permission(role, "acknowledge_alerts")
    data_source = get_active_data_source()

    st.caption(f"منبع داده: {data_source.upper()} | هشدارها: PostgreSQL")

    st.markdown("### هشدارهای بلادرنگ (WebSocket)")
    try:
        from dashboards.utils.live_alerts import render_live_alert_feed
        render_live_alert_feed()
    except Exception as exc:
        st.warning(f"WebSocket feed unavailable: {exc}")

    try:
        alerts = _load_db_alerts()
        using_db = True
    except Exception as exc:
        st.warning(f"اتصال به PostgreSQL برای هشدارها برقرار نشد: {exc}")
        alerts = pd.DataFrame()
        using_db = False

    if alerts.empty and using_db:
        st.info(
            "هشدار فعالی در پایگاه داده نیست. ابتدا ETL و ML pipeline را اجرا کنید:\n\n"
            "`python -m barekat.etl.pipeline` سپس `python -m barekat.ml.pipeline`"
        )
        return

    if alerts.empty:
        return

    severity_counts = alerts["severity"].value_counts() if "severity" in alerts.columns else pd.Series(dtype=int)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("کل هشدارها", len(alerts))
    with c2:
        st.metric("بحرانی", int(severity_counts.get("critical", 0)))
    with c3:
        st.metric("بالا", int(severity_counts.get("high", 0)))
    with c4:
        st.metric("متوسط", int(severity_counts.get("medium", 0)))

    severity_filter = st.multiselect(
        "فیلتر شدت",
        options=["critical", "high", "medium", "low"],
        default=["critical", "high", "medium"],
        format_func=lambda x: SEVERITY_FA.get(x, x),
    )

    dept_options = sorted(alerts["department"].dropna().unique().tolist()) if "department" in alerts.columns else []
    dept_filter = st.multiselect("فیلتر بخش", options=dept_options, default=dept_options)

    filtered = alerts[alerts["severity"].isin(severity_filter)]
    if dept_filter and "department" in filtered.columns:
        filtered = filtered[filtered["department"].isin(dept_filter)]

    for _, row in filtered.head(25).iterrows():
        severity = row.get("severity", "low")
        badge_class = f"badge-{severity}"
        severity_label = SEVERITY_FA.get(severity, severity)
        risk = row.get("risk_score", 0)
        st.markdown(
            f"""
            <div class="section-card">
                <span class="badge {badge_class}">{severity_label}</span>
                &nbsp; <strong>{row.get('message', '')}</strong><br>
                <small>
                بیمار: {row.get('patient_id', '-')} |
                بستری: {row.get('admission_id', '-')} |
                بخش: {row.get('department', '-')} |
                ریسک: {float(risk):.0%}
                </small>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if can_ack and row.get("alert_id"):
            if st.button("تأیید هشدار", key=f"ack_{row['alert_id']}"):
                if _acknowledge(int(row["alert_id"])):
                    st.success("هشدار تأیید شد.")
                    st.rerun()
                else:
                    st.error("تأیید هشدار ناموفق بود.")

    st.markdown("### جدول هشدارها")
    show_cols = [
        c for c in [
            "alert_id", "patient_id", "admission_id", "department",
            "severity", "risk_score", "message", "created_at",
        ]
        if c in filtered.columns
    ]
    display = filtered[show_cols].copy()
    if "severity" in display.columns:
        display["severity"] = display["severity"].map(SEVERITY_FA)
    st.dataframe(display, use_container_width=True, hide_index=True)

    csv = filtered[show_cols].to_csv(index=False).encode("utf-8-sig")
    st.download_button("دانلود هشدارها (CSV)", csv, "barekat_alerts.csv", "text/csv")
