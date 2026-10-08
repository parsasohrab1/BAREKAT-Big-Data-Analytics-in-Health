"""Patient population analytics page."""

import streamlit as st
import pandas as pd
import plotly.express as px

from dashboards.utils.charts import bar_chart, donut_chart
from dashboards.utils.styles import render_hero


def render(data: dict, master: pd.DataFrame, kpis: dict) -> None:
    patients = data.get("patients", pd.DataFrame())
    render_hero("Patient Population", "Demographic analysis, risk factors and clinical characteristics of patients")

    if patients.empty:
        st.info("Patient data is not available.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Average age", f"{patients['Age'].mean():.1f}")
    with c2:
        st.metric("Average BMI", f"{patients['BMI'].mean():.1f}")
    with c3:
        st.metric("Diabetes rate", f"{patients['Diabetes'].mean() * 100:.1f}%")
    with c4:
        st.metric("Hypertension rate", f"{patients['Hypertension'].mean() * 100:.1f}%")

    row1_l, row1_r = st.columns(2)
    with row1_l:
        age_bins = pd.cut(patients["Age"], bins=[0, 30, 45, 60, 75, 100], labels=["<30", "30-45", "45-60", "60-75", "75+"])
        age_dist = age_bins.value_counts().reset_index()
        age_dist.columns = ["Age_Group", "Count"]
        st.plotly_chart(bar_chart(age_dist, x="Age_Group", y="Count", title="Age group distribution"), use_container_width=True)

    with row1_r:
        gender = patients["Gender"].value_counts().reset_index()
        gender.columns = ["Gender", "Count"]
        st.plotly_chart(donut_chart(gender, "Gender", "Count", "Gender distribution"), use_container_width=True)

    row2_l, row2_r = st.columns(2)
    with row2_l:
        smoking = patients["Smoking_Status"].value_counts().reset_index()
        smoking.columns = ["Status", "Count"]
        st.plotly_chart(donut_chart(smoking, "Status", "Count", "Smoking status"), use_container_width=True)

    with row2_r:
        blood = patients["Blood_Type"].value_counts().reset_index()
        blood.columns = ["Blood_Type", "Count"]
        st.plotly_chart(bar_chart(blood, x="Blood_Type", y="Count", title="Blood type"), use_container_width=True)

    st.markdown("### Risk factor matrix")
    risk_matrix = pd.crosstab(patients["Diabetes"], patients["Hypertension"])
    risk_matrix.index = ["No diabetes", "Diabetes"]
    risk_matrix.columns = ["No hypertension", "Hypertension"]
    fig = px.imshow(
        risk_matrix,
        text_auto=True,
        color_continuous_scale="Teal",
        title="Co-occurrence of diabetes and hypertension",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Patient records")
    st.dataframe(patients, use_container_width=True, hide_index=True)
