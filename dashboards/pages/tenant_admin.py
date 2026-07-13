"""Tenant administration — quota, billing, settings per hospital."""

from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

from dashboards.utils.auth import get_current_user, has_permission
from dashboards.utils.styles import render_hero

API_BASE = os.getenv("BAREKAT_API_URL", "http://localhost:8000")


def _headers() -> dict:
    user = get_current_user() or {}
    token = user.get("token") or st.session_state.get("token")
    h = {}
    if token:
        h["Authorization"] = f"Bearer {token}"
    tid = st.session_state.get("tenant_id") or user.get("tenant_id")
    if tid:
        h["X-Tenant-ID"] = tid
    return h


def _api_get(path: str) -> dict | None:
    try:
        r = requests.get(f"{API_BASE}{path}", headers=_headers(), timeout=10)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


def render(data: dict, master: pd.DataFrame, kpis: dict) -> None:
    render_hero("مدیریت مراکز (Multi-Tenancy)", "جداسازی داده، تنظیمات اختصاصی، billing و quota")

    user = get_current_user() or {}
    role = user.get("role", "viewer")

    if not has_permission(role, "manage_tenants") and not user.get("is_platform_admin"):
        st.warning("فقط مدیر پلتفرم به این صفحه دسترسی دارد.")
        return

    tab_tenants, tab_quota, tab_billing, tab_settings = st.tabs([
        "مراکز", "Quota", "صورتحساب", "تنظیمات داشبورد",
    ])

    with tab_tenants:
        tenants_data = _api_get("/api/v1/tenants/")
        if tenants_data and tenants_data.get("tenants"):
            df = pd.DataFrame(tenants_data["tenants"])
            cols = [c for c in ["tenant_id", "name_fa", "plan_id", "status", "contact_email"] if c in df.columns]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)
        else:
            st.info("API در دسترس نیست — مراکز نمونه: default, tehran-general, isfahan-medical, mashhad-university")

        if user.get("is_platform_admin"):
            st.markdown("#### تعویض مرکز (Platform Admin)")
            options = ["default", "tehran-general", "isfahan-medical", "mashhad-university"]
            selected = st.selectbox("مرکز فعال", options, index=options.index(st.session_state.get("tenant_id", "default")))
            if st.button("اعمال مرکز"):
                st.session_state["tenant_id"] = selected
                user["tenant_id"] = selected
                st.session_state["user"] = user
                st.cache_data.clear()
                st.rerun()

    with tab_quota:
        quota = _api_get("/api/v1/tenants/me/quota")
        if quota and quota.get("quotas"):
            for metric, q in quota["quotas"].items():
                pct = min(q.get("pct", 0), 100)
                st.markdown(f"**{metric}** — {q['used']:,} / {q['limit']:,}")
                st.progress(pct / 100)
            if quota.get("any_exceeded"):
                st.error("یک یا چند quota تجاوز شده است.")
        else:
            st.markdown("""
            | متریک | استارتر | حرفه‌ای | سازمانی |
            |-------|---------|---------|---------|
            | بیماران | 5K | 25K | 100K |
            | بستری | 20K | 100K | 500K |
            | API calls/mo | 50K | 250K | 1M |
            """)

    with tab_billing:
        billing = _api_get("/api/v1/tenants/me/billing")
        if billing:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("پایه ماهانه (USD)", f"${billing.get('base_monthly_usd', 0):.0f}")
            with c2:
                st.metric("Overage", f"${billing.get('overage_usd', 0):.2f}")
            with c3:
                st.metric("تخمین کل", f"${billing.get('estimated_total_usd', 0):.2f}")
        else:
            st.info("اتصال به API برای مشاهده صورتحساب")

        plans = _api_get("/api/v1/tenants/plans")
        if plans and plans.get("plans"):
            st.markdown("#### پلن‌های موجود")
            st.dataframe(pd.DataFrame(plans["plans"]), use_container_width=True, hide_index=True)

    with tab_settings:
        me = _api_get("/api/v1/tenants/me")
        if me:
            settings = me.get("settings", {})
            st.markdown(f"**عنوان داشبورد:** {settings.get('dashboard_title', '—')}")
            st.markdown(f"**رنگ اصلی:** `{settings.get('primary_color', '#0891B2')}`")
            st.markdown(f"**صفحات فعال:** {', '.join(settings.get('enabled_pages', []))}")
            st.markdown(f"**پروفایل FHIR:** {settings.get('fhir_profile', 'iran_moh')}")

            with st.form("tenant_settings"):
                title = st.text_input("عنوان داشبورد", value=settings.get("dashboard_title", ""))
                color = st.color_picker("رنگ اصلی", settings.get("primary_color", "#0891B2"))
                if st.form_submit_button("ذخیره"):
                    try:
                        r = requests.patch(
                            f"{API_BASE}/api/v1/tenants/me/settings",
                            headers=_headers(),
                            json={"dashboard_title": title, "primary_color": color},
                            timeout=10,
                        )
                        if r.status_code == 200:
                            st.success("ذخیره شد")
                        else:
                            st.error(r.text[:200])
                    except requests.RequestException as exc:
                        st.error(str(exc))
        else:
            st.info("تنظیمات از API بارگذاری نمی‌شود — در حالت dev از session tenant استفاده می‌شود.")
