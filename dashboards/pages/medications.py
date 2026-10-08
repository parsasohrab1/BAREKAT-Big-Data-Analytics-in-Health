"""Medications analytics page."""

import streamlit as st
import pandas as pd

from dashboards.utils.charts import bar_chart, donut_chart
from dashboards.utils.styles import render_hero


def render(data: dict, master: pd.DataFrame, kpis: dict) -> None:
    medications = data.get("medications", pd.DataFrame())
    render_hero("Medications and Prescriptions", "Analysis of drug prescribing patterns, dose and frequency of use")

    if medications.empty:
        st.info("Medication data is not available.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total prescriptions", f"{len(medications):,}")
    with c2:
        st.metric("Unique medications", medications["Medication_Name"].nunique())
    with c3:
        st.metric("Average medications/admission", f"{medications.groupby('Admission_ID').size().mean():.1f}")

    col_l, col_r = st.columns(2)
    with col_l:
        meds = medications["Medication_Name"].value_counts().head(10).reset_index()
        meds.columns = ["Medication", "Count"]
        st.plotly_chart(
            bar_chart(meds, x="Count", y="Medication", title="Most-prescribed medications", orientation="h"),
            use_container_width=True,
        )

    with col_r:
        freq = medications["Frequency"].value_counts().reset_index()
        freq.columns = ["Frequency", "Count"]
        st.plotly_chart(donut_chart(freq, "Frequency", "Count", "Frequency of use"), use_container_width=True)

    if not master.empty:
        top_meds = medications["Medication_Name"].value_counts().head(5).index.tolist()
        subset = medications[medications["Medication_Name"].isin(top_meds)].merge(
            master[["Admission_ID", "Department"]], on="Admission_ID", how="left"
        )
        dept_med = subset.groupby(["Department", "Medication_Name"]).size().reset_index(name="Count")
        import plotly.express as px
        fig = px.treemap(dept_med, path=["Department", "Medication_Name"], values="Count", title="Medication map by department")
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(medications.sort_values("Prescribed_Date", ascending=False), use_container_width=True, hide_index=True)
