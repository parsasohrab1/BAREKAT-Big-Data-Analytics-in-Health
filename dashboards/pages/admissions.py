"""Admissions and departments analytics page."""

import streamlit as st
import pandas as pd
import plotly.express as px

from dashboards.utils.charts import bar_chart, donut_chart, heatmap_chart
from dashboards.utils.styles import render_hero


def render(data: dict, master: pd.DataFrame, kpis: dict) -> None:
    admissions = data.get("admissions", pd.DataFrame())
    render_hero("Admissions and Departments", "Analysis of admissions, length of stay, ICU and hospital department performance")

    if admissions.empty:
        st.info("Admission data is not available.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total admissions", f"{len(admissions):,}")
    with c2:
        st.metric("Average LOS", f"{admissions['Length_of_Stay'].mean():.1f} days")
    with c3:
        st.metric("Maximum LOS", f"{admissions['Length_of_Stay'].max()} days")
    with c4:
        st.metric("ICU rate", f"{admissions['ICU_Required'].mean() * 100:.1f}%")

    tab1, tab2, tab3 = st.tabs(["Departments", "Length of stay", "Admission type"])

    with tab1:
        col_l, col_r = st.columns(2)
        with col_l:
            dept = admissions["Department"].value_counts().reset_index()
            dept.columns = ["Department", "Count"]
            st.plotly_chart(
                bar_chart(dept, x="Department", y="Count", title="Number of admissions by department"),
                use_container_width=True,
            )
        with col_r:
            readmit_dept = admissions.groupby("Department")["Readmission_Flag"].mean().reset_index()
            readmit_dept.columns = ["Department", "Readmission_Rate"]
            readmit_dept["Readmission_Rate"] = (readmit_dept["Readmission_Rate"] * 100).round(1)
            st.plotly_chart(
                bar_chart(readmit_dept.sort_values("Readmission_Rate", ascending=False), x="Department", y="Readmission_Rate", title="Readmission rate by department"),
                use_container_width=True,
            )

        if not master.empty:
            pivot = pd.crosstab(master["Department"], master["Admission_Type"])
            st.plotly_chart(
                heatmap_chart(pivot.values, list(pivot.columns), list(pivot.index), "Department × admission type matrix"),
                use_container_width=True,
            )

    with tab2:
        fig = px.box(
            admissions,
            x="Department",
            y="Length_of_Stay",
            color="Department",
            title="Distribution of length of stay by department",
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        los_hist = admissions["Length_of_Stay"].value_counts().reset_index()
        los_hist.columns = ["LOS", "Count"]
        los_hist = los_hist.sort_values("LOS").head(20)
        st.plotly_chart(bar_chart(los_hist, x="LOS", y="Count", title="Length of stay frequency"), use_container_width=True)

    with tab3:
        col_l, col_r = st.columns(2)
        with col_l:
            adm_type = admissions["Admission_Type"].value_counts().reset_index()
            adm_type.columns = ["Type", "Count"]
            st.plotly_chart(donut_chart(adm_type, "Type", "Count", "Admission type"), use_container_width=True)
        with col_r:
            icu_by_type = admissions.groupby("Admission_Type")["ICU_Required"].mean().reset_index()
            icu_by_type.columns = ["Type", "ICU_Rate"]
            icu_by_type["ICU_Rate"] = (icu_by_type["ICU_Rate"] * 100).round(1)
            st.plotly_chart(bar_chart(icu_by_type, x="Type", y="ICU_Rate", title="ICU rate by admission type"), use_container_width=True)

    st.markdown("### Admission details")
    st.dataframe(admissions.sort_values("Admission_Date", ascending=False), use_container_width=True, hide_index=True)
