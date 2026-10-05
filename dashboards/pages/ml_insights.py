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
        "ML Analytics",
        "LOS prediction, mortality/sepsis alerts, physician note NLP, vital signs monitoring",
    )

    model_catalog = pd.DataFrame([
        {"Model": "Readmission + SHAP", "Use": "High-risk explanation / printable report", "endpoint": "/api/v1/ml/predict/readmission/explain/{id}"},
        {"Model": "LOS", "Use": "Bed planning", "endpoint": "/api/v1/ml/predict/los"},
        {"Model": "Mortality / Sepsis", "Use": "Early warning", "endpoint": "/api/v1/ml/predict/early-warning"},
        {"Model": "Note NLP", "Use": "Diagnosis extraction", "endpoint": "/api/v1/ml/nlp/extract-diagnoses"},
        {"Model": "Vital signs", "Use": "Real-time monitoring", "endpoint": "/api/v1/ml/vitals/monitor/{id}"},
    ])
    st.dataframe(model_catalog, use_container_width=True, hide_index=True)

    try:
        from barekat.ml.registry import get_active_model
        active = get_active_model("readmission")
        if active and active.get("metrics"):
            test_m = active["metrics"].get("test", {})
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Model version", active.get("version", "—"))
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
        st.warning("Admission data is required to run the models.")
        return

    with st.spinner("Training/loading models..."):
        model, encoders, risk_scores = train_readmission_model(master)
        clusters = cluster_patients(data, n_clusters=5)

    master_ml = master.copy()
    master_ml["risk_score"] = risk_scores.reindex(master_ml.index)

    c1, c2, c3, c4 = st.columns(4)
    high_risk = (master_ml["risk_score"] >= 0.7).sum()
    with c1:
        st.metric("Average risk", f"{master_ml['risk_score'].mean():.0%}")
    with c2:
        st.metric("High-risk patients", f"{high_risk:,}")
    with c3:
        st.metric("Clusters", clusters["cluster"].nunique() if not clusters.empty else 0)
    with c4:
        actual = master_ml["Readmission_Flag"].mean() * 100 if "Readmission_Flag" in master_ml.columns else 0
        st.metric("Actual readmission rate", f"{actual:.1f}%")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "Readmission",
        "Clustering",
        "LOS prediction",
        "Mortality/sepsis alert",
        "Note NLP",
        "Vital signs",
        "Feature importance",
    ])

    with tab1:
        col_l, col_r = st.columns(2)
        with col_l:
            risk_bins = pd.cut(
                master_ml["risk_score"],
                bins=[0, 0.3, 0.5, 0.7, 0.9, 1.0],
                labels=["Very low", "Low", "Medium", "High", "Critical"],
            )
            risk_dist = risk_bins.value_counts().reset_index()
            risk_dist.columns = ["Risk_Level", "Count"]
            st.plotly_chart(donut_chart(risk_dist, "Risk_Level", "Count", "Risk level distribution"), use_container_width=True)

        with col_r:
            dept_risk = master_ml.groupby("Department")["risk_score"].mean().reset_index()
            dept_risk.columns = ["Department", "Avg_Risk"]
            dept_risk["Avg_Risk"] = (dept_risk["Avg_Risk"] * 100).round(1)
            st.plotly_chart(
                bar_chart(dept_risk.sort_values("Avg_Risk", ascending=False), x="Department", y="Avg_Risk", title="Average risk by department"),
                use_container_width=True,
            )

        threshold = st.slider("Risk alert threshold", 0.5, 0.95, 0.7, 0.05)
        alerts = build_alerts(master_ml, master_ml["risk_score"], threshold=threshold)
        st.markdown(f"### High-risk admissions ({len(alerts)} cases)")
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
            st.markdown("### Why is this patient high-risk? (SHAP)")
            st.caption("Model explanation for clinical acceptance — factors affecting the readmission prediction")

            id_col = "Admission_ID" if "Admission_ID" in alerts.columns else "admission_id"
            admission_options = alerts[id_col].astype(str).tolist()
            selected_admission = st.selectbox(
                "Select a high-risk admission",
                admission_options,
                format_func=lambda x: f"{x} — risk {alerts.loc[alerts[id_col].astype(str) == x, 'risk_score'].iloc[0]:.0%}",
            )

            if selected_admission:
                with st.spinner("Computing SHAP..."):
                    explanation = explain_admission_from_master(data, selected_admission)

                if explanation:
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("Predicted risk", explanation.get("risk_percent", "—"))
                    with c2:
                        sev = explanation.get("severity", "low")
                        sev_fa = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"}.get(sev, sev)
                        st.metric("Risk level", sev_fa)
                    with c3:
                        st.metric("Department threshold", f"{explanation.get('threshold', 0):.0%}")

                    st.info(explanation.get("summary_fa", ""))

                    col_chart, col_factors = st.columns([1.2, 1])
                    with col_chart:
                        st.plotly_chart(shap_waterfall_chart(explanation), use_container_width=True)
                    with col_factors:
                        st.markdown("**Factors increasing risk:**")
                        for f in explanation.get("top_risk_factors", [])[:5]:
                            st.markdown(
                                f"- **{f['label_fa']}** = {f['value']} "
                                f"(`{f['shap_value']:+.3f}`)"
                            )
                        prot = explanation.get("protective_factors", [])
                        if prot:
                            st.markdown("**Factors decreasing risk:**")
                            for f in prot[:3]:
                                st.markdown(
                                    f"- {f['label_fa']} = {f['value']} "
                                    f"(`{f['shap_value']:+.3f}`)"
                                )

                    report_html = generate_report_html(explanation)
                    st.download_button(
                        "📄 Download printable report (HTML)",
                        data=report_html,
                        file_name=f"readmission_report_{selected_admission}.html",
                        mime="text/html",
                        use_container_width=True,
                    )
                    with st.expander("Printable report preview"):
                        st.components.v1.html(report_html, height=600, scrolling=True)
                else:
                    st.warning(
                        "No trained model is available. Run `python -m barekat.ml.pipeline`."
                    )
        else:
            st.success("No admission with risk above the threshold was found.")

    with tab2:
        if clusters.empty:
            st.info("There is not enough data for clustering.")
        else:
            col_l, col_r = st.columns(2)
            with col_l:
                cluster_sizes = clusters["cluster"].value_counts().reset_index()
                cluster_sizes.columns = ["Cluster", "Count"]
                cluster_sizes["Cluster"] = cluster_sizes["Cluster"].astype(str)
                st.plotly_chart(bar_chart(cluster_sizes, x="Cluster", y="Count", title="Cluster sizes"), use_container_width=True)

            with col_r:
                if "age" in clusters.columns and "bmi" in clusters.columns:
                    fig = px.scatter(
                        clusters,
                        x="age",
                        y="bmi",
                        color=clusters["cluster"].astype(str),
                        title="Cluster map (age × BMI)",
                        labels={"color": "Cluster"},
                    )
                    st.plotly_chart(fig, use_container_width=True)

            st.markdown("### Cluster profiles")
            profile_cols = [c for c in clusters.columns if c not in ("patient_id", "cluster")]
            if profile_cols:
                profile = clusters.groupby("cluster")[profile_cols].mean().round(2)
                st.dataframe(profile, use_container_width=True)

    with tab3:
        los_df = predict_los(data)
        if los_df.empty:
            st.info("The LOS model has not been trained or there is not enough data. Run `python -m barekat.ml.pipeline`.")
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Average predicted LOS", f"{los_df['predicted_los'].mean():.1f} days")
            with c2:
                long_stay = (los_df["predicted_los"] >= 10).sum()
                st.metric("Long stays (≥10 days)", f"{long_stay:,}")
            with c3:
                if "actual_los" in los_df.columns:
                    err = (los_df["predicted_los"] - los_df["actual_los"]).abs().mean()
                    st.metric("MAE", f"{err:.1f} days")
            st.plotly_chart(
                bar_chart(
                    los_df.groupby("department")["predicted_los"].mean().reset_index().rename(
                        columns={"department": "Department", "predicted_los": "Avg_LOS"},
                    ),
                    x="Department",
                    y="Avg_LOS",
                    title="Predicted LOS by department (bed planning)",
                ),
                use_container_width=True,
            )
            st.dataframe(los_df.head(20), use_container_width=True, hide_index=True)

    with tab4:
        ew_df = predict_early_warning(data)
        if ew_df.empty:
            st.info("The early warning model is not available.")
        else:
            col_l, col_r = st.columns(2)
            with col_l:
                st.metric("Average mortality risk", f"{ew_df['mortality_risk'].mean():.0%}")
                high_mort = (ew_df["mortality_risk"] >= 0.6).sum()
                st.metric("Mortality alert", f"{high_mort:,}")
            with col_r:
                st.metric("Average sepsis risk", f"{ew_df['sepsis_risk'].mean():.0%}")
                high_sep = (ew_df["sepsis_risk"] >= 0.6).sum()
                st.metric("Sepsis alert", f"{high_sep:,}")
            scatter_df = ew_df.copy()
            scatter_df["mortality_pct"] = scatter_df["mortality_risk"] * 100
            scatter_df["sepsis_pct"] = scatter_df["sepsis_risk"] * 100
            fig = px.scatter(
                scatter_df.head(500),
                x="mortality_pct",
                y="sepsis_pct",
                color="department",
                title="Mortality risk × sepsis map",
                labels={"mortality_pct": "Mortality %", "sepsis_pct": "Sepsis %"},
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab5:
        nlp_df = demo_nlp_extract(data, limit=8)
        if nlp_df.empty:
            st.info("No clinical notes found. Generate the data with `generate_data.py`.")
        else:
            st.markdown("### Diagnosis extraction from physician notes (NLP)")
            st.dataframe(nlp_df, use_container_width=True, hide_index=True)
            sample_note = st.text_area(
                "Sample note for extraction",
                "Patient with sepsis and elevated lactate. History of COPD. Suspected septic shock.",
            )
            if st.button("Extract ICD"):
                from barekat.ml.nlp_notes import ClinicalNotesNLP
                nlp = ClinicalNotesNLP()
                nlp.load()
                hits = nlp.extract_diagnoses(sample_note)
                st.json(hits)

    with tab6:
        vitals_df = score_vitals(data)
        if vitals_df.empty:
            st.info("No vital signs data found.")
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Average NEWS", f"{vitals_df['news_score'].mean():.1f}")
            with c2:
                st.metric("Average deterioration", f"{vitals_df['deterioration_score'].mean():.0%}")
            with c3:
                critical = (vitals_df["deterioration_score"] >= 0.7).sum()
                st.metric("Critical", f"{critical:,}")
            st.plotly_chart(
                bar_chart(
                    vitals_df.groupby("department")["deterioration_score"].mean().reset_index().rename(
                        columns={"department": "Department", "deterioration_score": "Score"},
                    ),
                    x="Department",
                    y="Score",
                    title="Deterioration score by department",
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
                title="Feature importance in readmission prediction",
                color_discrete_sequence=["#0891B2"],
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("There is no sufficiently trained model to show feature importance.")
