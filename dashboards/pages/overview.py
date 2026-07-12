"""Overview dashboard page."""

import streamlit as st
import pandas as pd

from dashboards.utils.charts import bar_chart, donut_chart, gauge_chart, line_chart
from dashboards.utils.styles import render_hero


def render(data: dict, master: pd.DataFrame, kpis: dict) -> None:
    render_hero(
        "نمای کلی پلتفرم",
        "شاخص‌های کلیدی عملکرد، روند بستری و وضعیت کلی سیستم تحلیل سلامت",
    )

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    metrics = [
        (c1, "بیماران", f"{kpis['patients']:,}"),
        (c2, "بستری‌ها", f"{kpis['admissions']:,}"),
        (c3, "تشخیص‌ها", f"{kpis['diagnoses']:,}"),
        (c4, "داروها", f"{kpis['medications']:,}"),
        (c5, "آزمایش‌ها", f"{kpis['lab_results']:,}"),
        (c6, "بخش‌ها", f"{kpis['departments']:,}"),
    ]
    for col, label, value in metrics:
        with col:
            st.metric(label, value)

    st.markdown("<br>", unsafe_allow_html=True)

    g1, g2, g3, g4 = st.columns(4)
    with g1:
        st.plotly_chart(gauge_chart(kpis["readmit_rate"], "نرخ بستری مجدد"), use_container_width=True)
    with g2:
        st.plotly_chart(gauge_chart(kpis["icu_rate"], "نرخ ICU"), use_container_width=True)
    with g3:
        st.plotly_chart(gauge_chart(kpis["abnormal_rate"], "نتایج غیرطبیعی آزمایش"), use_container_width=True)
    with g4:
        st.metric("میانگین مدت بستری (روز)", f"{kpis['avg_los']:.1f}")

    if not master.empty:
        left, right = st.columns(2)

        with left:
            dept = master["Department"].value_counts().reset_index()
            dept.columns = ["Department", "Count"]
            st.plotly_chart(
                bar_chart(dept.head(8), x="Count", y="Department", title="بستری‌ها بر اساس بخش", orientation="h"),
                use_container_width=True,
            )

        with right:
            if "admission_month" in master.columns:
                trend = master.groupby("admission_month").size().reset_index(name="count")
                st.plotly_chart(
                    line_chart(trend, x="admission_month", y="count", title="روند ماهانه بستری"),
                    use_container_width=True,
                )

        row2_l, row2_r = st.columns(2)
        with row2_l:
            adm_type = master["Admission_Type"].value_counts().reset_index()
            adm_type.columns = ["Type", "Count"]
            st.plotly_chart(donut_chart(adm_type, "Type", "Count", "نوع پذیرش"), use_container_width=True)

        with row2_r:
            icu = master.groupby("Department")["ICU_Required"].mean().reset_index()
            icu.columns = ["Department", "ICU_Rate"]
            icu["ICU_Rate"] = (icu["ICU_Rate"] * 100).round(1)
            st.plotly_chart(
                bar_chart(icu.sort_values("ICU_Rate", ascending=False).head(8), x="Department", y="ICU_Rate", title="نرخ ICU به تفکیک بخش"),
                use_container_width=True,
            )

        st.markdown("### جدول خلاصه بستری‌های اخیر")
        display_cols = [
            c for c in [
                "Admission_ID", "Patient_ID", "Department", "Admission_Type",
                "Length_of_Stay", "ICU_Required", "Readmission_Flag", "Admission_Date",
            ]
            if c in master.columns
        ]
        st.dataframe(
            master[display_cols].sort_values("Admission_Date", ascending=False).head(20),
            use_container_width=True,
            hide_index=True,
        )
