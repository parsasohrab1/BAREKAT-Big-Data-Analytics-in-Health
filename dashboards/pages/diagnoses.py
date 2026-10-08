"""Diagnoses analytics page."""

import streamlit as st
import pandas as pd

from dashboards.utils.charts import bar_chart, donut_chart
from dashboards.utils.styles import render_hero


def render(data: dict, master: pd.DataFrame, kpis: dict) -> None:
    diagnoses = data.get("diagnoses", pd.DataFrame())
    render_hero("Clinical Diagnoses", "Analysis of ICD-10 codes, primary diagnoses and disease patterns")

    if diagnoses.empty:
        st.info("Diagnosis data is not available.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total diagnoses", f"{len(diagnoses):,}")
    with c2:
        st.metric("Unique ICD codes", diagnoses["ICD_Code"].nunique())
    with c3:
        primary_rate = diagnoses["Primary_Diagnosis"].mean() * 100 / max(diagnoses.groupby("Admission_ID").size().mean(), 1)
        st.metric("Average diagnoses/admission", f"{diagnoses.groupby('Admission_ID').size().mean():.1f}")

    col_l, col_r = st.columns(2)
    with col_l:
        icd = diagnoses["ICD_Code"].value_counts().head(10).reset_index()
        icd.columns = ["ICD_Code", "Count"]
        st.plotly_chart(
            bar_chart(icd, x="ICD_Code", y="Count", title="Top 10 ICD-10 codes"),
            use_container_width=True,
        )

    with col_r:
        desc = diagnoses.groupby("Diagnosis_Description").size().reset_index(name="Count")
        desc = desc.sort_values("Count", ascending=False).head(8)
        st.plotly_chart(
            bar_chart(desc, x="Count", y="Diagnosis_Description", title="Most frequent diagnoses", orientation="h"),
            use_container_width=True,
        )

    if not master.empty:
        top_icd = diagnoses["ICD_Code"].value_counts().head(5).index.tolist()
        subset = diagnoses[diagnoses["ICD_Code"].isin(top_icd)].merge(
            master[["Admission_ID", "Department"]], on="Admission_ID", how="left"
        )
        dept_icd = subset.groupby(["Department", "ICD_Code"]).size().reset_index(name="Count")
        import plotly.express as px
        fig = px.sunburst(dept_icd, path=["Department", "ICD_Code"], values="Count", title="Diagnosis map by department")
        st.plotly_chart(fig, use_container_width=True)

    primary = diagnoses["Primary_Diagnosis"].value_counts().reset_index()
    primary.columns = ["Primary", "Count"]
    primary["Primary"] = primary["Primary"].map({True: "Primary", False: "Secondary"})
    st.plotly_chart(donut_chart(primary, "Primary", "Count", "Primary vs. secondary diagnosis"), use_container_width=True)

    st.dataframe(diagnoses, use_container_width=True, hide_index=True)
