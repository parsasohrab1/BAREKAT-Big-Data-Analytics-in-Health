"""BAREKAT Health Analytics - Professional Dashboard."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from dashboards.utils.data_loader import (
    apply_filters,
    build_master_admissions,
    compute_kpis,
    load_raw_tables,
)
from dashboards.utils.styles import apply_styles
from dashboards.pages import (
    admissions as admissions_page,
    alerts as alerts_page,
    diagnoses as diagnoses_page,
    infrastructure as infrastructure_page,
    laboratory as laboratory_page,
    medications as medications_page,
    ml_insights as ml_insights_page,
    overview as overview_page,
    patients as patients_page,
)

PAGES = {
    "نمای کلی": overview_page,
    "جمعیت بیماران": patients_page,
    "بستری و بخش‌ها": admissions_page,
    "تشخیص‌ها": diagnoses_page,
    "داروها": medications_page,
    "آزمایشگاه": laboratory_page,
    "هوش تحلیلی ML": ml_insights_page,
    "هشدارها": alerts_page,
    "زیرساخت": infrastructure_page,
}


@st.cache_data(show_spinner=False)
def load_dashboard_data():
    data = load_raw_tables()
    master = build_master_admissions(data)
    kpis = compute_kpis(data)
    return data, master, kpis


def render_sidebar(master):
    st.sidebar.markdown("## BAREKAT")
    st.sidebar.caption("Big Data Analytics in Health")
    st.sidebar.divider()

    page = st.sidebar.radio("منوی اصلی", list(PAGES.keys()), label_visibility="collapsed")

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
    st.sidebar.markdown(
        """
        **راهنما**
        - داده از `data/raw` بارگذاری می‌شود
        - مدل‌های ML در مرورگر آموزش می‌بینند
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

    data, master, kpis = load_dashboard_data()

    if not data:
        st.markdown(
            """
            <div class="hero-banner">
                <h1>BAREKAT Health Analytics</h1>
                <p>داده‌ای یافت نشد. ابتدا داده سنتتیک تولید کنید.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.code("python scripts/generate_data.py --patients 1000 --admissions 3000", language="bash")
        st.stop()

    page_name, departments, genders, admission_types = render_sidebar(master)
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
    PAGES[page_name].render(filtered_data, filtered_master, filtered_kpis)


if __name__ == "__main__":
    main()
