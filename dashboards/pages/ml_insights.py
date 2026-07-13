"""ML insights page - readmission and clustering."""

import streamlit as st
import pandas as pd
import plotly.express as px

from dashboards.utils.charts import bar_chart, donut_chart
from dashboards.utils.ml_analytics import (
    build_alerts,
    cluster_patients,
    demo_nlp_extract,
    predict_early_warning,
    predict_los,
    score_vitals,
    train_readmission_model,
)
from dashboards.utils.shap_explainer import (
    explain_admission_from_master,
    generate_report_html,
    shap_waterfall_chart,
)
from dashboards.utils.styles import render_hero


def render(data: dict, master: pd.DataFrame, kpis: dict) -> None:
    render_hero(
        "هوش تحلیلی و ML",
        "پیش‌بینی LOS، هشدار مرگ‌ومیر/سپسیس، NLP یادداشت پزشک، مانیتورینگ علائم حیاتی",
    )

    model_catalog = pd.DataFrame([
        {"مدل": "بستری مجدد + SHAP", "کاربرد": "توضیح پرخطر / گزارش چاپی", "endpoint": "/api/v1/ml/predict/readmission/explain/{id}"},
        {"مدل": "LOS", "کاربرد": "برنامه‌ریزی تخت", "endpoint": "/api/v1/ml/predict/los"},
        {"مدل": "مرگ‌ومیر / سپسیس", "کاربرد": "هشدار زودهنگام", "endpoint": "/api/v1/ml/predict/early-warning"},
        {"مدل": "NLP یادداشت", "کاربرد": "استخراج تشخیص", "endpoint": "/api/v1/ml/nlp/extract-diagnoses"},
        {"مدل": "علائم حیاتی", "کاربرد": "مانیتورینگ لحظه‌ای", "endpoint": "/api/v1/ml/vitals/monitor/{id}"},
    ])
    st.dataframe(model_catalog, use_container_width=True, hide_index=True)

    try:
        from barekat.ml.registry import get_active_model
        active = get_active_model("readmission")
        if active and active.get("metrics"):
            test_m = active["metrics"].get("test", {})
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("نسخه مدل", active.get("version", "—"))
            with m2:
                st.metric("Test AUC", test_m.get("auc", "—"))
            with m3:
                st.metric("Test F1", test_m.get("f1", "—"))
            with m4:
                cal = test_m.get("calibration", {})
                brier = cal.get("brier_score", "—")
                st.metric("Brier Score", brier)
    except Exception:
        pass

    if master.empty:
        st.warning("برای اجرای مدل‌ها به داده بستری نیاز است.")
        return

    with st.spinner("در حال آموزش/بارگذاری مدل‌ها..."):
        model, encoders, risk_scores = train_readmission_model(master)
        clusters = cluster_patients(data, n_clusters=5)

    master_ml = master.copy()
    master_ml["risk_score"] = risk_scores.reindex(master_ml.index)

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

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "بستری مجدد",
        "خوشه‌بندی",
        "پیش‌بینی LOS",
        "هشدار مرگ‌ومیر/سپسیس",
        "NLP یادداشت",
        "علائم حیاتی",
        "اهمیت ویژگی‌ها",
    ])

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

            st.divider()
            st.markdown("### چرا این بیمار پرخطر است؟ (SHAP)")
            st.caption("توضیح مدل برای پذیرش بالینی — عوامل مؤثر بر پیش‌بینی بستری مجدد")

            id_col = "Admission_ID" if "Admission_ID" in alerts.columns else "admission_id"
            admission_options = alerts[id_col].astype(str).tolist()
            selected_admission = st.selectbox(
                "انتخاب بستری پرخطر",
                admission_options,
                format_func=lambda x: f"{x} — ریسک {alerts.loc[alerts[id_col].astype(str) == x, 'risk_score'].iloc[0]:.0%}",
            )

            if selected_admission:
                with st.spinner("محاسبه SHAP..."):
                    explanation = explain_admission_from_master(data, selected_admission)

                if explanation:
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("ریسک پیش‌بینی", explanation.get("risk_percent", "—"))
                    with c2:
                        sev = explanation.get("severity", "low")
                        sev_fa = {"critical": "بحرانی", "high": "بالا", "medium": "متوسط", "low": "پایین"}.get(sev, sev)
                        st.metric("سطح خطر", sev_fa)
                    with c3:
                        st.metric("آستانه بخش", f"{explanation.get('threshold', 0):.0%}")

                    st.info(explanation.get("summary_fa", ""))

                    col_chart, col_factors = st.columns([1.2, 1])
                    with col_chart:
                        st.plotly_chart(shap_waterfall_chart(explanation), use_container_width=True)
                    with col_factors:
                        st.markdown("**عوامل افزایش ریسک:**")
                        for f in explanation.get("top_risk_factors", [])[:5]:
                            st.markdown(
                                f"- **{f['label_fa']}** = {f['value']} "
                                f"(`{f['shap_value']:+.3f}`)"
                            )
                        prot = explanation.get("protective_factors", [])
                        if prot:
                            st.markdown("**عوامل کاهش ریسک:**")
                            for f in prot[:3]:
                                st.markdown(
                                    f"- {f['label_fa']} = {f['value']} "
                                    f"(`{f['shap_value']:+.3f}`)"
                                )

                    report_html = generate_report_html(explanation)
                    st.download_button(
                        "📄 دانلود گزارش قابل چاپ (HTML)",
                        data=report_html,
                        file_name=f"readmission_report_{selected_admission}.html",
                        mime="text/html",
                        use_container_width=True,
                    )
                    with st.expander("پیش‌نمایش گزارش چاپی"):
                        st.components.v1.html(report_html, height=600, scrolling=True)
                else:
                    st.warning(
                        "مدل آموزش‌دیده در دسترس نیست. `python -m barekat.ml.pipeline` را اجرا کنید."
                    )
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
        los_df = predict_los(data)
        if los_df.empty:
            st.info("مدل LOS آموزش ندیده یا داده کافی نیست. `python -m barekat.ml.pipeline` را اجرا کنید.")
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("میانگین LOS پیش‌بینی", f"{los_df['predicted_los'].mean():.1f} روز")
            with c2:
                long_stay = (los_df["predicted_los"] >= 10).sum()
                st.metric("بستری‌های طولانی (≥10 روز)", f"{long_stay:,}")
            with c3:
                if "actual_los" in los_df.columns:
                    err = (los_df["predicted_los"] - los_df["actual_los"]).abs().mean()
                    st.metric("MAE", f"{err:.1f} روز")
            st.plotly_chart(
                bar_chart(
                    los_df.groupby("department")["predicted_los"].mean().reset_index().rename(
                        columns={"department": "Department", "predicted_los": "Avg_LOS"},
                    ),
                    x="Department",
                    y="Avg_LOS",
                    title="LOS پیش‌بینی‌شده به تفکیک بخش (برنامه‌ریزی تخت)",
                ),
                use_container_width=True,
            )
            st.dataframe(los_df.head(20), use_container_width=True, hide_index=True)

    with tab4:
        ew_df = predict_early_warning(data)
        if ew_df.empty:
            st.info("مدل هشدار زودهنگام در دسترس نیست.")
        else:
            col_l, col_r = st.columns(2)
            with col_l:
                st.metric("میانگین ریسک مرگ‌ومیر", f"{ew_df['mortality_risk'].mean():.0%}")
                high_mort = (ew_df["mortality_risk"] >= 0.6).sum()
                st.metric("هشدار مرگ‌ومیر", f"{high_mort:,}")
            with col_r:
                st.metric("میانگین ریسک سپسیس", f"{ew_df['sepsis_risk'].mean():.0%}")
                high_sep = (ew_df["sepsis_risk"] >= 0.6).sum()
                st.metric("هشدار سپسیس", f"{high_sep:,}")
            scatter_df = ew_df.copy()
            scatter_df["mortality_pct"] = scatter_df["mortality_risk"] * 100
            scatter_df["sepsis_pct"] = scatter_df["sepsis_risk"] * 100
            fig = px.scatter(
                scatter_df.head(500),
                x="mortality_pct",
                y="sepsis_pct",
                color="department",
                title="نقشه ریسک مرگ‌ومیر × سپسیس",
                labels={"mortality_pct": "Mortality %", "sepsis_pct": "Sepsis %"},
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab5:
        nlp_df = demo_nlp_extract(data, limit=8)
        if nlp_df.empty:
            st.info("یادداشت بالینی یافت نشد. داده را با `generate_data.py` تولید کنید.")
        else:
            st.markdown("### استخراج تشخیص از یادداشت پزشک (NLP)")
            st.dataframe(nlp_df, use_container_width=True, hide_index=True)
            sample_note = st.text_area(
                "یادداشت نمونه برای استخراج",
                "Patient with sepsis and elevated lactate. History of COPD. Suspected septic shock.",
            )
            if st.button("استخراج ICD"):
                from barekat.ml.nlp_notes import ClinicalNotesNLP
                nlp = ClinicalNotesNLP()
                nlp.load()
                hits = nlp.extract_diagnoses(sample_note)
                st.json(hits)

    with tab6:
        vitals_df = score_vitals(data)
        if vitals_df.empty:
            st.info("داده علائم حیاتی یافت نشد.")
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("میانگین NEWS", f"{vitals_df['news_score'].mean():.1f}")
            with c2:
                st.metric("میانگین deterioration", f"{vitals_df['deterioration_score'].mean():.0%}")
            with c3:
                critical = (vitals_df["deterioration_score"] >= 0.7).sum()
                st.metric("بحرانی", f"{critical:,}")
            st.plotly_chart(
                bar_chart(
                    vitals_df.groupby("department")["deterioration_score"].mean().reset_index().rename(
                        columns={"department": "Department", "deterioration_score": "Score"},
                    ),
                    x="Department",
                    y="Score",
                    title="امتیاز deterioration به تفکیک بخش",
                ),
                use_container_width=True,
            )
            st.dataframe(vitals_df.sort_values("deterioration_score", ascending=False).head(20), use_container_width=True, hide_index=True)

    with tab7:
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
