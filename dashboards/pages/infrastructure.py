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
        "زیرساخت و خط لوله داده",
        "وضعیت منابع داده، ETL، ذخیره‌سازی و سرویس‌های پلتفرم",
    )

    user = get_current_user() or {}
    data_source = get_active_data_source()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("منبع داده", data_source.upper())
    with c2:
        st.metric("جداول بارگذاری‌شده", len(data))
    with c3:
        st.metric("رکوردهای کل", sum(len(df) for df in data.values()))
    with c4:
        try:
            from barekat.services.alerts import alert_count_by_severity
            alert_counts = alert_count_by_severity()
            st.metric("هشدارهای فعال", sum(alert_counts.values()))
        except Exception:
            st.metric("هشدارهای فعال", "—")

    st.markdown("### وضعیت منابع داده")
    rows = []
    for name, df in data.items():
        file_path = DATA_DIR / f"{name}.csv"
        rows.append({
            "منبع": name,
            "رکورد": len(df),
            "ستون": len(df.columns),
            "فایل": str(file_path),
            "وضعیت": "فعال" if file_path.exists() else "ناموجود",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("### معماری پلتفرم")
    st.markdown(
        """
        | لایه | فناوری | نقش |
        |------|--------|-----|
        | Ingestion | CSV / HL7 / DICOM | ورود داده‌های ناهمگن |
        | ETL | Python Pipeline | استخراج، تبدیل، بارگذاری |
        | Storage | PostgreSQL + MinIO | انبار داده و فایل |
        | Streaming | Kafka | رویدادهای بلادرنگ |
        | Processing | Spark | پردازش توزیع‌شده |
        | ML | scikit-learn | پیش‌بینی و خوشه‌بندی |
        | API | FastAPI + RBAC | دسترسی امن |
        | Dashboard | Streamlit | تجسم تعاملی |
        """
    )

    st.markdown("### قابلیت‌های فعال")
    features = [
        ("تولید داده سنتتیک", True, "Patients, Admissions, Diagnoses, Medications, Lab Results"),
        ("خط لوله ETL", True, "Extract → Transform → Load به PostgreSQL"),
        ("بارگذاری Incremental", True, "Upsert + watermark در staging.etl_watermarks"),
        ("اعتبارسنجی Schema", True, "Great Expectations پیش از بارگذاری"),
        ("زمان‌بندی ETL", True, "Celery Beat: ساعتی incremental، روزانه full"),
        ("لاگ و Retry", True, "audit.etl_runs با retry خودکار"),
        ("پیش‌بینی بستری مجدد", True, "Gradient Boosting Classifier"),
        ("خوشه‌بندی بیماران", True, "K-Means بر اساس ویژگی‌های بالینی"),
        ("هشدارهای پیش‌بینی‌کننده", True, "analytics.predictive_alerts"),
        ("کنترل دسترسی RBAC", True, "admin / clinician / researcher / viewer"),
    ]

    for name, active, desc in features:
        icon = "✅" if active else "⏳"
        st.markdown(f"- {icon} **{name}** — {desc}")

    st.markdown("### تاریخچه اجرای ETL")
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
            st.info("هنوز اجرای ETL ثبت نشده است.")
    except Exception as exc:
        st.warning(f"نمایش لاگ ETL نیاز به PostgreSQL دارد: {exc}")

    if not master.empty:
        st.markdown("### کیفیت داده")
        quality = {
            "بستری بدون بیمار": int(master["Patient_ID"].isna().sum()),
            "LOS منفی": int((master["Length_of_Stay"] < 0).sum()) if "Length_of_Stay" in master.columns else 0,
            "فیلدهای خالی Department": int(master["Department"].isna().sum()),
        }
        qdf = pd.DataFrame([{"بررسی": k, "تعداد": v, "وضعیت": "✅" if v == 0 else "⚠️"} for k, v in quality.items()])
        st.dataframe(qdf, use_container_width=True, hide_index=True)

    st.info(
        "ETL: `python -m barekat.etl.pipeline --mode incremental` | "
        "Celery: `make worker` + `make beat` | "
        "ML: `python -m barekat.ml.pipeline`"
    )
