"""Diagnoses analytics page."""

import streamlit as st
import pandas as pd

from dashboards.utils.charts import bar_chart, donut_chart
from dashboards.utils.styles import render_hero


def render(data: dict, master: pd.DataFrame, kpis: dict) -> None:
    diagnoses = data.get("diagnoses", pd.DataFrame())
    render_hero("تشخیص‌های بالینی", "تحلیل کدهای ICD-10، تشخیص‌های اصلی و الگوهای بیماری")

    if diagnoses.empty:
        st.info("داده تشخیص موجود نیست.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("کل تشخیص‌ها", f"{len(diagnoses):,}")
    with c2:
        st.metric("کدهای ICD منحصربفرد", diagnoses["ICD_Code"].nunique())
    with c3:
        primary_rate = diagnoses["Primary_Diagnosis"].mean() * 100 / max(diagnoses.groupby("Admission_ID").size().mean(), 1)
        st.metric("میانگین تشخیص/بستری", f"{diagnoses.groupby('Admission_ID').size().mean():.1f}")

    col_l, col_r = st.columns(2)
    with col_l:
        icd = diagnoses["ICD_Code"].value_counts().head(10).reset_index()
        icd.columns = ["ICD_Code", "Count"]
        st.plotly_chart(
            bar_chart(icd, x="ICD_Code", y="Count", title="۱۰ کد ICD-10 پرتکرار"),
            use_container_width=True,
        )

    with col_r:
        desc = diagnoses.groupby("Diagnosis_Description").size().reset_index(name="Count")
        desc = desc.sort_values("Count", ascending=False).head(8)
        st.plotly_chart(
            bar_chart(desc, x="Count", y="Diagnosis_Description", title="تشخیص‌های پرتکرار", orientation="h"),
            use_container_width=True,
        )

    if not master.empty:
        top_icd = diagnoses["ICD_Code"].value_counts().head(5).index.tolist()
        subset = diagnoses[diagnoses["ICD_Code"].isin(top_icd)].merge(
            master[["Admission_ID", "Department"]], on="Admission_ID", how="left"
        )
        dept_icd = subset.groupby(["Department", "ICD_Code"]).size().reset_index(name="Count")
        import plotly.express as px
        fig = px.sunburst(dept_icd, path=["Department", "ICD_Code"], values="Count", title="نقشه تشخیص به تفکیک بخش")
        st.plotly_chart(fig, use_container_width=True)

    primary = diagnoses["Primary_Diagnosis"].value_counts().reset_index()
    primary.columns = ["Primary", "Count"]
    primary["Primary"] = primary["Primary"].map({True: "اصلی", False: "فرعی"})
    st.plotly_chart(donut_chart(primary, "Primary", "Count", "تشخیص اصلی در مقابل فرعی"), use_container_width=True)

    st.dataframe(diagnoses, use_container_width=True, hide_index=True)
