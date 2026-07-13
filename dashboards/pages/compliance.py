"""Compliance & Privacy dashboard page — HIPAA / GDPR / domestic."""

from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

from dashboards.utils.auth import get_current_user, has_permission
from dashboards.utils.styles import render_hero

API_BASE = os.getenv("BAREKAT_API_URL", "http://localhost:8000")


def _api_headers() -> dict:
    user = get_current_user() or {}
    token = user.get("token") or st.session_state.get("token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _api_get(path: str) -> dict | list | None:
    try:
        resp = requests.get(f"{API_BASE}{path}", headers=_api_headers(), timeout=10)
        if resp.status_code == 200:
            return resp.json()
        st.warning(f"API {path}: {resp.status_code}")
    except requests.RequestException as exc:
        st.info(f"API در دسترس نیست ({API_BASE}) — {exc}")
    return None


def _api_post(path: str) -> dict | None:
    try:
        resp = requests.post(f"{API_BASE}{path}", headers=_api_headers(), timeout=30)
        if resp.status_code == 200:
            return resp.json()
        st.error(f"خطا: {resp.status_code} — {resp.text[:200]}")
    except requests.RequestException as exc:
        st.error(f"API: {exc}")
    return None


def render(data: dict, master: pd.DataFrame, kpis: dict) -> None:
    render_hero(
        "انطباق و حریم خصوصی",
        "HIPAA / GDPR / قوانین داخلی — audit trail، نگهداری داده، ناشناس‌سازی",
    )

    user = get_current_user() or {}
    role = user.get("role", "viewer")

    # Log dashboard page access
    if token := st.session_state.get("token"):
        try:
            requests.post(
                f"{API_BASE}/api/v1/compliance/dashboard-audit",
                headers={"Authorization": f"Bearer {token}"},
                json={"page": "انطباق و حریم خصوصی", "action": "page_view"},
                timeout=5,
            )
        except requests.RequestException:
            pass

    tab_summary, tab_audit, tab_retention, tab_privacy = st.tabs([
        "چارچوب‌های قانونی",
        "لاگ دسترسی",
        "نگهداری داده",
        "ناشناس‌سازی",
    ])

    with tab_summary:
        st.markdown("### چارچوب‌های انطباق")
        summary = _api_get("/api/v1/compliance/summary") if has_permission(role, "manage_users") else None
        if summary:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("پوشش انطباق", f"{summary.get('coverage_pct', 0)}%")
            with c2:
                st.metric("پیاده‌سازی‌شده", summary.get("implemented_count", 0))
            with c3:
                st.metric("کل الزامات", summary.get("total_count", 0))

            for fw_key, fw in summary.get("frameworks", {}).items():
                with st.expander(f"{fw.get('name_fa', fw_key)} ({fw.get('name', '')})"):
                    st.caption(fw.get("scope", ""))
                    for reg in fw.get("regulations", []):
                        st.markdown(f"- {reg}")

            reqs = summary.get("requirements", [])
            if reqs:
                df = pd.DataFrame(reqs)
                df["وضعیت"] = df["implemented"].map({True: "✅", False: "⏳"})
                st.dataframe(
                    df[["title_fa", "framework", "وضعیت", "config_key"]],
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            frameworks = _api_get("/api/v1/compliance/frameworks")
            if frameworks:
                for key, fw in frameworks.get("frameworks", {}).items():
                    st.markdown(f"**{fw.get('name_fa', key)}** — {fw.get('scope', '')}")
            else:
                st.markdown("""
                **چارچوب‌های پشتیبانی‌شده:**
                - **HIPAA** — کنترل دسترسی، audit trail، حداقل ضرورت
                - **GDPR** — رضایت، حق حذف، pseudonymization، retention
                - **قوانین داخلی** — SEPAS، کد ملی، مصوبات وزارت بهداشت
                """)

    with tab_audit:
        st.markdown("### لاگ دسترسی (چه کسی، چه زمانی، به چه داده‌ای)")
        if not has_permission(role, "manage_users"):
            st.warning("فقط مدیر می‌تواند لاگ دسترسی را ببیند.")
        else:
            logs_data = _api_get("/api/v1/compliance/audit-logs?limit=50")
            if logs_data and logs_data.get("data"):
                df = pd.DataFrame(logs_data["data"])
                cols = [c for c in [
                    "timestamp", "username", "role", "action", "resource",
                    "patient_id", "status_code", "ip_address",
                ] if c in df.columns]
                st.dataframe(df[cols], use_container_width=True, hide_index=True)
                st.caption(f"کل: {logs_data.get('total', 0)} رکورد")
            else:
                st.info("هنوز لاگی ثبت نشده — با استفاده از API و داشبورد، لاگ‌ها اینجا نمایش داده می‌شوند.")

    with tab_retention:
        st.markdown("### سیاست نگهداری و حذف خودکار")
        if has_permission(role, "manage_users"):
            policies = _api_get("/api/v1/compliance/retention/policies")
            if policies:
                pdf = pd.DataFrame(policies.get("policies", []))
                if not pdf.empty:
                    st.dataframe(
                        pdf[["data_category", "retention_days", "regulation_ref", "description_fa", "auto_purge"]],
                        use_container_width=True,
                        hide_index=True,
                    )

            if st.button("اجرای purge دستی", type="primary"):
                result = _api_post("/api/v1/compliance/retention/purge")
                if result:
                    st.success(f"وضعیت: {result.get('status')} — {result.get('affected', {})}")

            jobs = _api_get("/api/v1/compliance/retention/jobs?limit=10")
            if jobs and jobs.get("jobs"):
                st.markdown("#### تاریخچه حذف")
                st.dataframe(pd.DataFrame(jobs["jobs"]), use_container_width=True, hide_index=True)
        else:
            st.info("سیاست نگهداری: یادداشت بالینی ۷ سال، آزمایش ۵ سال، DICOM ۱۰ سال، لاگ دسترسی ۶ سال.")

    with tab_privacy:
        st.markdown("### ناشناس‌سازی / شناسه‌سازی مجدد")
        if not has_permission(role, "manage_users"):
            st.warning("عملیات privacy فقط برای مدیر.")
        else:
            patient_id = st.text_input("شناسه بیمار", placeholder="PT00001")
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("Pseudonymize") and patient_id:
                    r = _api_post(f"/api/v1/compliance/pseudonymize/{patient_id}")
                    if r:
                        st.json(r)
            with c2:
                if st.button("Anonymize") and patient_id:
                    if st.checkbox("تأیید — غیرقابل بازگشت", key="anon_confirm"):
                        r = _api_post(f"/api/v1/compliance/anonymize/{patient_id}")
                        if r:
                            st.json(r)
            with c3:
                if st.button("Erasure (GDPR)") and patient_id:
                    if st.checkbox("تأیید حذف کامل", key="erase_confirm"):
                        r = _api_post(f"/api/v1/compliance/erasure/{patient_id}")
                        if r:
                            st.json(r)

            st.divider()
            st.markdown("#### ثبت رضایت‌نامه")
            with st.form("consent_form"):
                cp = st.text_input("بیمار", key="consent_patient")
                purpose = st.text_input("هدف", value="تحقیقات بالینی")
                basis = st.selectbox("مبنای قانونی", [
                    "consent", "treatment", "research", "legal_obligation",
                ])
                granted = st.checkbox("رضایت داده شده", value=True)
                if st.form_submit_button("ثبت"):
                    try:
                        resp = requests.post(
                            f"{API_BASE}/api/v1/compliance/consent",
                            headers=_api_headers(),
                            json={
                                "patient_id": cp,
                                "purpose": purpose,
                                "lawful_basis": basis,
                                "granted": granted,
                            },
                            timeout=10,
                        )
                        if resp.status_code == 200:
                            st.success("ثبت شد")
                        else:
                            st.error(resp.text[:200])
                    except requests.RequestException as exc:
                        st.error(str(exc))
