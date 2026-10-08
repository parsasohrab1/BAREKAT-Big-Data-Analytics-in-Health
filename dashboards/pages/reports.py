"""Weekly reports and manager notifications dashboard page."""

import streamlit as st

from dashboards.utils.auth import get_current_user, has_permission
from dashboards.utils.styles import render_hero


def render(data, master, kpis) -> None:
    render_hero(
        "Management Reports",
        "Weekly PDF/Excel report, critical alert email/SMS settings",
    )

    user = get_current_user() or {}
    role = user.get("role", "viewer")
    can_export = has_permission(role, "export")
    is_admin = role in ("admin", "platform_admin")

    tab_summary, tab_prefs, tab_log = st.tabs(["Weekly report", "Notification settings", "Delivery log"])

    with tab_summary:
        try:
            from barekat.services.reports import collect_weekly_metrics, generate_excel_report, generate_pdf_report

            tenant_id = st.session_state.get("tenant_id", "default")
            metrics = collect_weekly_metrics(tenant_id)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Weekly admissions", metrics.get("admissions_total", 0))
            c2.metric("Readmission %", metrics.get("readmission_rate_pct", 0))
            c3.metric("Critical alerts", metrics.get("alerts_critical", 0))
            c4.metric("Average LOS", metrics.get("avg_length_of_stay", 0))

            st.caption(f"Period: {metrics.get('period_start')} — {metrics.get('period_end')}")

            if can_export:
                col1, col2, col3 = st.columns(3)
                excel_bytes = generate_excel_report(metrics)
                pdf_bytes = generate_pdf_report(metrics)
                col1.download_button(
                    "Download Excel",
                    data=excel_bytes,
                    file_name=f"weekly_{tenant_id}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                col2.download_button(
                    "Download PDF",
                    data=pdf_bytes,
                    file_name=f"weekly_{tenant_id}.pdf",
                    mime="application/pdf",
                )
                if is_admin:
                    if col3.button("Send immediately to managers"):
                        from barekat.worker.tasks import run_weekly_reports
                        run_weekly_reports.delay()
                        st.success("The weekly report has been queued in Celery")
            else:
                st.info("Downloading the report requires the researcher or admin role.")

            if metrics.get("top_departments"):
                st.markdown("#### Busiest departments")
                st.dataframe(metrics["top_departments"], use_container_width=True, hide_index=True)

        except Exception as exc:
            st.warning(f"Loading report: {exc}")

    with tab_prefs:
        if not is_admin:
            st.info("Only an administrator can change notification settings.")
        else:
            with st.form("notif_pref"):
                email = st.text_input("Manager email", placeholder="manager@hospital.ir")
                phone = st.text_input("Mobile (SMS)", placeholder="09121234567")
                min_sev = st.selectbox("Minimum alert severity", ["critical", "high", "medium"], index=0)
                email_on = st.checkbox("Email", value=True)
                sms_on = st.checkbox("SMS", value=True)
                weekly = st.checkbox("Weekly report", value=True)
                if st.form_submit_button("Save"):
                    try:
                        from sqlalchemy import text
                        from barekat.storage.database import engine

                        tenant_id = st.session_state.get("tenant_id", "default")
                        with engine.begin() as conn:
                            conn.execute(
                                text("""
                                    INSERT INTO tenant.notification_preferences
                                        (tenant_id, user_email, phone, email_enabled, sms_enabled,
                                         alert_min_severity, weekly_report)
                                    VALUES (:tenant_id, :email, :phone, :email_on, :sms_on, :min_sev, :weekly)
                                    ON CONFLICT (tenant_id, user_email) DO UPDATE SET
                                        phone = EXCLUDED.phone,
                                        email_enabled = EXCLUDED.email_enabled,
                                        sms_enabled = EXCLUDED.sms_enabled,
                                        alert_min_severity = EXCLUDED.alert_min_severity,
                                        weekly_report = EXCLUDED.weekly_report,
                                        updated_at = NOW()
                                """),
                                {
                                    "tenant_id": tenant_id,
                                    "email": email,
                                    "phone": phone or None,
                                    "email_on": email_on,
                                    "sms_on": sms_on,
                                    "min_sev": min_sev,
                                    "weekly": weekly,
                                },
                            )
                        st.success("Settings saved")
                    except Exception as exc:
                        st.error(str(exc))

            st.markdown("#### Mobile PWA")
            st.markdown(
                "Mobile dashboard: [http://localhost:8000/mobile/](http://localhost:8000/mobile/) "
                "— installable on iOS/Android"
            )

    with tab_log:
        if is_admin:
            try:
                from sqlalchemy import text
                from barekat.storage.database import engine

                with engine.connect() as conn:
                    rows = conn.execute(
                        text("""
                            SELECT channel, recipient_masked, subject, severity, status, created_at
                            FROM audit.notification_log ORDER BY created_at DESC LIMIT 50
                        """)
                    ).mappings().all()
                if rows:
                    st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
                else:
                    st.info("No notification has been sent yet (NOTIFICATIONS_ENABLED=false in dev)")
            except Exception as exc:
                st.warning(str(exc))
        else:
            st.info("The notification log is for administrators only")
