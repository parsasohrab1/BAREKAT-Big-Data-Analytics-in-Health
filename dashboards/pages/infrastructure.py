"""Platform infrastructure and data pipeline status page."""

import os
from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd

from dashboards.utils.auth import get_current_user
from dashboards.utils.data_loader import get_active_data_source
from dashboards.utils.styles import render_hero

DATA_DIR = Path(os.getenv("DATA_DIR", "./data/raw"))
MODELS_DIR = Path(os.getenv("MODELS_DIR", "./data/models"))


def render(data: dict, master: pd.DataFrame, kpis: dict) -> None:
    render_hero(
        "Infrastructure and Data Pipeline",
        "Status of data sources, ETL, storage and platform services",
    )

    user = get_current_user() or {}
    data_source = get_active_data_source()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Data source", data_source.upper())
    with c2:
        st.metric("Loaded tables", len(data))
    with c3:
        st.metric("Total records", sum(len(df) for df in data.values()))
    with c4:
        try:
            from barekat.services.alerts import alert_count_by_severity
            alert_counts = alert_count_by_severity()
            st.metric("Active alerts", sum(alert_counts.values()))
        except Exception:
            st.metric("Active alerts", "—")

    st.markdown("### Data source status")
    rows = []
    for name, df in data.items():
        file_path = DATA_DIR / f"{name}.csv"
        rows.append({
            "Source": name,
            "Records": len(df),
            "Columns": len(df.columns),
            "File": str(file_path),
            "Status": "Active" if file_path.exists() else "Unavailable",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("### Platform architecture")
    st.markdown(
        """
        | Layer | Technology | Role |
        |------|--------|-----|
        | Ingestion | CSV / HL7 / DICOM | Heterogeneous data ingestion |
        | ETL | Python Pipeline | Extract, transform, load |
        | Storage | PostgreSQL + MinIO | Data warehouse and files |
        | Streaming | Kafka | Real-time events |
        | Processing | Spark | Distributed processing |
        | ML | scikit-learn | Prediction and clustering |
        | API | FastAPI + RBAC | Secure access |
        | Dashboard | Streamlit | Interactive visualization |
        """
    )

    st.markdown("### Active capabilities")
    features = [
        ("Synthetic data generation", True, "Patients, Admissions, Diagnoses, Medications, Lab Results"),
        ("ETL pipeline", True, "Extract → Transform → Load into PostgreSQL"),
        ("Incremental loading", True, "Upsert + watermark in staging.etl_watermarks"),
        ("Schema validation", True, "Great Expectations before loading"),
        ("ETL scheduling", True, "Celery Beat: hourly incremental, daily full"),
        ("Logging and Retry", True, "audit.etl_runs with automatic retry"),
        ("Readmission prediction", True, "Gradient Boosting Classifier"),
        ("Patient clustering", True, "K-Means based on clinical features"),
        ("Predictive alerts", True, "analytics.predictive_alerts"),
        ("RBAC access control", True, "admin / clinician / researcher / viewer"),
    ]

    for name, active, desc in features:
        icon = "✅" if active else "⏳"
        st.markdown(f"- {icon} **{name}** — {desc}")

    st.markdown("### ETL run history")
    try:
        from barekat.etl.run_logger import get_recent_runs
        runs = get_recent_runs(limit=15)
        if runs:
            runs_df = pd.DataFrame(runs)
            display_cols = [
                c for c in [
                    "run_id", "status", "mode", "started_at", "finished_at",
                    "retry_count", "records_loaded", "error_message",
                ]
                if c in runs_df.columns
            ]
            st.dataframe(runs_df[display_cols], use_container_width=True, hide_index=True)
        else:
            st.info("No ETL run has been recorded yet.")
    except Exception as exc:
        st.warning(f"Displaying the ETL log requires PostgreSQL: {exc}")

    if not master.empty:
        st.markdown("### Data quality")
        quality = {
            "Admissions without a patient": int(master["Patient_ID"].isna().sum()),
            "Negative LOS": int((master["Length_of_Stay"] < 0).sum()) if "Length_of_Stay" in master.columns else 0,
            "Empty Department fields": int(master["Department"].isna().sum()),
        }
        qdf = pd.DataFrame([{"Check": k, "Count": v, "Status": "✅" if v == 0 else "⚠️"} for k, v in quality.items()])
        st.dataframe(qdf, use_container_width=True, hide_index=True)

    st.info(
        "ETL: `python -m barekat.etl.pipeline --mode incremental` | "
        "Celery: `make worker` + `make beat` | "
        "ML: `python -m barekat.ml.pipeline`"
    )
