"""Patient population analytics page."""

import streamlit as st
import pandas as pd
import plotly.express as px

from dashboards.utils.charts import bar_chart, donut_chart
from dashboards.utils.styles import render_hero


def render(data: dict, master: pd.DataFrame, kpis: dict) -> None:
    patients = data.get("patients", pd.DataFrame())
    render_hero("جمعیت بیماران", "تحلیل جمعیت‌شناختی، عوامل خطر و ویژگی‌های بالینی بیماران")

    if patients.empty:
        st.info("داده بیماران موجود نیست.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("میانگین سن", f"{patients['Age'].mean():.1f}")
    with c2:
        st.metric("میانگین BMI", f"{patients['BMI'].mean():.1f}")
    with c3:
        st.metric("نرخ دیابت", f"{patients['Diabetes'].mean() * 100:.1f}%")
    with c4:
        st.metric("نرخ فشار خون", f"{patients['Hypertension'].mean() * 100:.1f}%")

    row1_l, row1_r = st.columns(2)
    with row1_l:
        age_bins = pd.cut(patients["Age"], bins=[0, 30, 45, 60, 75, 100], labels=["<30", "30-45", "45-60", "60-75", "75+"])
        age_dist = age_bins.value_counts().reset_index()
        age_dist.columns = ["Age_Group", "Count"]
        st.plotly_chart(bar_chart(age_dist, x="Age_Group", y="Count", title="توزیع گروه سنی"), use_container_width=True)

    with row1_r:
        gender = patients["Gender"].value_counts().reset_index()
        gender.columns = ["Gender", "Count"]
        st.plotly_chart(donut_chart(gender, "Gender", "Count", "توزیع جنسیتی"), use_container_width=True)

    row2_l, row2_r = st.columns(2)
    with row2_l:
        smoking = patients["Smoking_Status"].value_counts().reset_index()
        smoking.columns = ["Status", "Count"]
        st.plotly_chart(donut_chart(smoking, "Status", "Count", "وضعیت سیگار"), use_container_width=True)

    with row2_r:
        blood = patients["Blood_Type"].value_counts().reset_index()
        blood.columns = ["Blood_Type", "Count"]
        st.plotly_chart(bar_chart(blood, x="Blood_Type", y="Count", title="گروه خونی"), use_container_width=True)

    st.markdown("### ماتریس عوامل خطر")
    risk_matrix = pd.crosstab(patients["Diabetes"], patients["Hypertension"])
    risk_matrix.index = ["بدون دیابت", "دیابت"]
    risk_matrix.columns = ["بدون فشارخون", "فشارخون"]
    fig = px.imshow(
        risk_matrix,
        text_auto=True,
        color_continuous_scale="Teal",
        title="هم‌رخدادی دیابت و فشار خون",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### پرونده بیماران")
    st.dataframe(patients, use_container_width=True, hide_index=True)
