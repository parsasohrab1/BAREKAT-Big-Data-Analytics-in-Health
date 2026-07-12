"""ML insights page - readmission and clustering."""

import streamlit as st
import pandas as pd
import plotly.express as px

from dashboards.utils.charts import bar_chart, donut_chart
from dashboards.utils.ml_analytics import build_alerts, cluster_patients, train_readmission_model
from dashboards.utils.styles import render_hero


def render(data: dict, master: pd.DataFrame, kpis: dict) -> None:
    render_hero(
        "هوش تحلیلی و ML",
        "پیش‌بینی بستری مجدد، خوشه‌بندی بیماران و امتیازدهی ریسک",
    )

    if master.empty:
        st.warning("برای اجرای مدل‌ها به داده بستری نیاز است.")
        return

    with st.spinner("در حال آموزش/بارگذاری مدل‌ها..."):
        model, encoders, risk_scores = train_readmission_model(master)
        clusters = cluster_patients(data, n_clusters=5)

    master_ml = master.copy()
    master_ml["risk_score"] = risk_scores.values

    c1, c2, c3, c4 = st.columns(4)
    high_risk = (master_ml["risk_score"] >= 0.7).sum()
    with c1:
        st.metric("میانگین ریسک", f"{master_ml['risk_score'].mean():.0%}")
    with c2:
        st.metric("بیماران پرخطر", f"{high_risk:,}")
    with c3:
        st.metric("خوشه‌ها", clusters["cluster"].nunique() if not clusters.empty else 0)
    with c4:
        actual = master_ml["Readmission_Flag"].mean() * 100 if "Readmission_Flag" in master_ml.columns else 0
        st.metric("نرخ واقعی بستری مجدد", f"{actual:.1f}%")

    tab1, tab2, tab3 = st.tabs(["پیش‌بینی بستری مجدد", "خوشه‌بندی بیماران", "اهمیت ویژگی‌ها"])

    with tab1:
        col_l, col_r = st.columns(2)
        with col_l:
            risk_bins = pd.cut(
                master_ml["risk_score"],
                bins=[0, 0.3, 0.5, 0.7, 0.9, 1.0],
                labels=["خیلی کم", "کم", "متوسط", "بالا", "بحرانی"],
            )
            risk_dist = risk_bins.value_counts().reset_index()
            risk_dist.columns = ["Risk_Level", "Count"]
            st.plotly_chart(donut_chart(risk_dist, "Risk_Level", "Count", "توزیع سطح ریسک"), use_container_width=True)

        with col_r:
            dept_risk = master_ml.groupby("Department")["risk_score"].mean().reset_index()
            dept_risk.columns = ["Department", "Avg_Risk"]
            dept_risk["Avg_Risk"] = (dept_risk["Avg_Risk"] * 100).round(1)
            st.plotly_chart(
                bar_chart(dept_risk.sort_values("Avg_Risk", ascending=False), x="Department", y="Avg_Risk", title="میانگین ریسک به تفکیک بخش"),
                use_container_width=True,
            )

        threshold = st.slider("آستانه هشدار ریسک", 0.5, 0.95, 0.7, 0.05)
        alerts = build_alerts(master_ml, master_ml["risk_score"], threshold=threshold)
        st.markdown(f"### بستری‌های پرخطر ({len(alerts)} مورد)")
        if not alerts.empty:
            show_cols = [
                c for c in [
                    "Admission_ID", "Patient_ID", "Department", "Length_of_Stay",
                    "risk_score", "severity", "Readmission_Flag",
                ]
                if c in alerts.columns
            ]
            st.dataframe(alerts[show_cols].head(30), use_container_width=True, hide_index=True)
        else:
            st.success("بستری با ریسک بالاتر از آستانه یافت نشد.")

    with tab2:
        if clusters.empty:
            st.info("داده کافی برای خوشه‌بندی وجود ندارد.")
        else:
            col_l, col_r = st.columns(2)
            with col_l:
                cluster_sizes = clusters["cluster"].value_counts().reset_index()
                cluster_sizes.columns = ["Cluster", "Count"]
                cluster_sizes["Cluster"] = cluster_sizes["Cluster"].astype(str)
                st.plotly_chart(bar_chart(cluster_sizes, x="Cluster", y="Count", title="اندازه خوشه‌ها"), use_container_width=True)

            with col_r:
                if "age" in clusters.columns and "bmi" in clusters.columns:
                    fig = px.scatter(
                        clusters,
                        x="age",
                        y="bmi",
                        color=clusters["cluster"].astype(str),
                        title="نقشه خوشه‌ها (سن × BMI)",
                        labels={"color": "Cluster"},
                    )
                    st.plotly_chart(fig, use_container_width=True)

            st.markdown("### پروفایل خوشه‌ها")
            profile_cols = [c for c in clusters.columns if c not in ("patient_id", "cluster")]
            if profile_cols:
                profile = clusters.groupby("cluster")[profile_cols].mean().round(2)
                st.dataframe(profile, use_container_width=True)

    with tab3:
        if hasattr(model, "feature_importances_"):
            importances = pd.DataFrame({
                "feature": model.feature_names_in_,
                "importance": model.feature_importances_,
            }).sort_values("importance", ascending=True)
            fig = px.bar(
                importances,
                x="importance",
                y="feature",
                orientation="h",
                title="اهمیت ویژگی‌ها در پیش‌بینی بستری مجدد",
                color_discrete_sequence=["#0891B2"],
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("مدل آموزش‌دیده کافی برای نمایش اهمیت ویژگی‌ها وجود ندارد.")
