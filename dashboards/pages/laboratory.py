"""Laboratory results analytics page."""

import streamlit as st
import pandas as pd
import plotly.express as px

from dashboards.utils.charts import bar_chart, donut_chart, gauge_chart
from dashboards.utils.styles import render_hero


def render(data: dict, master: pd.DataFrame, kpis: dict) -> None:
    lab_results = data.get("lab_results", pd.DataFrame())
    render_hero("نتایج آزمایشگاه", "تحلیل تست‌های آزمایشگاهی، نتایج غیرطبیعی و روندها")

    if lab_results.empty:
        st.info("داده آزمایشگاهی موجود نیست.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("کل تست‌ها", f"{len(lab_results):,}")
    with c2:
        st.metric("انواع تست", lab_results["Test_Name"].nunique())
    with c3:
        st.metric("غیرطبیعی", f"{lab_results['Abnormal_Flag'].sum():,}")
    with c4:
        st.metric("نرخ غیرطبیعی", f"{lab_results['Abnormal_Flag'].mean() * 100:.1f}%")

    col_l, col_r = st.columns([1, 2])
    with col_l:
        st.plotly_chart(
            gauge_chart(lab_results["Abnormal_Flag"].mean() * 100, "نرخ نتایج غیرطبیعی"),
            use_container_width=True,
        )

    with col_r:
        tests = lab_results["Test_Name"].value_counts().reset_index()
        tests.columns = ["Test", "Count"]
        st.plotly_chart(bar_chart(tests, x="Test", y="Count", title="فراوانی تست‌ها"), use_container_width=True)

    row2_l, row2_r = st.columns(2)
    with row2_l:
        abnormal_by_test = lab_results.groupby("Test_Name")["Abnormal_Flag"].mean().reset_index()
        abnormal_by_test.columns = ["Test", "Abnormal_Rate"]
        abnormal_by_test["Abnormal_Rate"] = (abnormal_by_test["Abnormal_Rate"] * 100).round(1)
        st.plotly_chart(
            bar_chart(abnormal_by_test.sort_values("Abnormal_Rate", ascending=False), x="Test", y="Abnormal_Rate", title="نرخ غیرطبیعی به تفکیک تست"),
            use_container_width=True,
        )

    with row2_r:
        abnormal = lab_results["Abnormal_Flag"].value_counts().reset_index()
        abnormal.columns = ["Flag", "Count"]
        abnormal["Flag"] = abnormal["Flag"].map({0: "طبیعی", 1: "غیرطبیعی"})
        st.plotly_chart(donut_chart(abnormal, "Flag", "Count", "وضعیت کلی نتایج"), use_container_width=True)

    st.markdown("### توزیع مقادیر تست‌ها")
    selected_test = st.selectbox("انتخاب تست", sorted(lab_results["Test_Name"].unique()))
    subset = lab_results[lab_results["Test_Name"] == selected_test]
    fig = px.histogram(subset, x="Result_Value", nbins=25, title=f"توزیع مقادیر {selected_test}", color_discrete_sequence=["#0891B2"])
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(lab_results.sort_values("Test_Date", ascending=False), use_container_width=True, hide_index=True)
