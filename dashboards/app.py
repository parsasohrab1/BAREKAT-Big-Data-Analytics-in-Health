"""BAREKAT Health Analytics - Professional Dashboard."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for path in (str(ROOT), str(SRC)):
    if path not in sys.path:
        sys.path.insert(0, path)

import streamlit as st

from dashboards.utils.auth import (
    filter_pages,
    is_authenticated,
    render_login_form,
    render_user_sidebar,
)
from dashboards.utils.data_loader import (
    apply_filters,
    build_master_admissions,
    compute_kpis,
    get_active_data_source,
    load_raw_tables,
)
from dashboards.utils.styles import apply_styles
from dashboards.pages import (
    admissions as admissions_page,
    alerts as alerts_page,
    compliance as compliance_page,
    diagnoses as diagnoses_page,
    infrastructure as infrastructure_page,
    laboratory as laboratory_page,
    medications as medications_page,
    ml_insights as ml_insights_page,
    overview as overview_page,
    patients as patients_page,
    imaging as imaging_page,
    tenant_admin as tenant_admin_page,
    reports as reports_page,
)

ALL_PAGES = {
    "نمای کلی": overview_page,
    "جمعیت بیماران": patients_page,
    "بستری و بخش‌ها": admissions_page,
    "تشخیص‌ها": diagnoses_page,
    "داروها": medications_page,
    "آزمایشگاه": laboratory_page,
    "هوش تحلیلی ML": ml_insights_page,
    "هشدارها": alerts_page,
    "تصاویر پزشکی": imaging_page,
    "انطباق و حریم خصوصی": compliance_page,
    "مدیریت مراکز": tenant_admin_page,
    "گزارش‌های مدیریتی": reports_page,
    "زیرساخت": infrastructure_page,
}


@st.cache_data(show_spinner="در حال بارگذاری داده...")
def load_dashboard_data(tenant_id: str = "default"):
    from barekat.tenant.context import TenantContext, set_current_tenant

    set_current_tenant(TenantContext(tenant_id=tenant_id, slug=tenant_id, name_fa=tenant_id))
    data = load_raw_tables(tenant_id=tenant_id)
    master = build_master_admissions(data)
    kpis = compute_kpis(data)
    source = get_active_data_source()
    set_current_tenant(None)
    return data, master, kpis, source


def render_sidebar(master, pages: dict):
    user = st.session_state.get("user", {})
    tenant_id = st.session_state.get("tenant_id") or user.get("tenant_id", "default")

    # Tenant branding
    try:
        from barekat.tenant.repository import get_tenant
        tenant = get_tenant(tenant_id)
        title = (tenant or {}).get("dashboard_title") or (tenant or {}).get("name_fa") or "BAREKAT"
        color = (tenant or {}).get("primary_color", "#0891B2")
    except Exception:
        title, color = "BAREKAT", "#0891B2"

    st.sidebar.markdown(f"## {title}")
    st.sidebar.markdown(f"<span style='color:{color}'>Big Data Analytics in Health</span>", unsafe_allow_html=True)
    st.sidebar.caption(f"Tenant: `{tenant_id}`")
    render_user_sidebar()
    st.sidebar.divider()

    page = st.sidebar.radio("منوی اصلی", list(pages.keys()), label_visibility="collapsed")

    st.sidebar.divider()
    st.sidebar.markdown("### فیلترها")

    departments = []
    genders = []
    admission_types = []

    if not master.empty:
        if "Department" in master.columns:
            departments = st.sidebar.multiselect(
                "بخش",
                sorted(master["Department"].dropna().unique()),
                default=sorted(master["Department"].dropna().unique()),
            )
        if "Gender" in master.columns:
            genders = st.sidebar.multiselect(
                "جنسیت",
                sorted(master["Gender"].dropna().unique()),
                default=sorted(master["Gender"].dropna().unique()),
            )
        if "Admission_Type" in master.columns:
            admission_types = st.sidebar.multiselect(
                "نوع پذیرش",
                sorted(master["Admission_Type"].dropna().unique()),
                default=sorted(master["Admission_Type"].dropna().unique()),
            )

    st.sidebar.divider()
    source = get_active_data_source()
    st.sidebar.markdown(
        f"""
        **راهنما**
        - منبع داده: `{source.upper()}`
        - هشدارها: PostgreSQL
        - API: `localhost:8000/docs`
        """
    )

    return page, departments, genders, admission_types


def main():
    st.set_page_config(
        page_title="BAREKAT Health Analytics",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_styles()

    if not is_authenticated():
        render_login_form()
        st.stop()

    user = st.session_state["user"]
    pages = filter_pages(ALL_PAGES, user.get("role", "viewer"))

    if not pages:
        st.error("نقش شما دسترسی به هیچ صفحه‌ای ندارد.")
        st.stop()

    data, master, kpis, source = load_dashboard_data(
        st.session_state.get("tenant_id") or user.get("tenant_id", "default")
    )

    if not data:
        st.markdown(
            """
            <div class="hero-banner">
                <h1>BAREKAT Health Analytics</h1>
                <p>داده‌ای یافت نشد.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if source == "postgres":
            st.code(
                "python scripts/generate_data.py\n"
                "python -m barekat.etl.pipeline",
                language="bash",
            )
        else:
            st.code("python scripts/generate_data.py --patients 1000 --admissions 3000", language="bash")
        st.stop()

    page_name, departments, genders, admission_types = render_sidebar(master, pages)
    filtered_master = apply_filters(master, departments, genders, admission_types)

    filtered_data = data.copy()
    if not filtered_master.empty and "admissions" in filtered_data:
        admission_ids = set(filtered_master["Admission_ID"])
        filtered_data["admissions"] = filtered_data["admissions"][
            filtered_data["admissions"]["Admission_ID"].isin(admission_ids)
        ]
        for key, id_col in [
            ("diagnoses", "Admission_ID"),
            ("medications", "Admission_ID"),
            ("lab_results", "Admission_ID"),
        ]:
            if key in filtered_data:
                filtered_data[key] = filtered_data[key][filtered_data[key][id_col].isin(admission_ids)]
        if "patients" in filtered_data:
            patient_ids = set(filtered_master["Patient_ID"])
            filtered_data["patients"] = filtered_data["patients"][
                filtered_data["patients"]["Patient_ID"].isin(patient_ids)
            ]

    filtered_kpis = compute_kpis(filtered_data)
    pages[page_name].render(filtered_data, filtered_master, filtered_kpis)


if __name__ == "__main__":
    main()
