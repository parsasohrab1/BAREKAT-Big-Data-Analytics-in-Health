"""Platform infrastructure and data pipeline status page."""

import os
from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd

from dashboards.utils.styles import render_hero

DATA_DIR = Path(os.getenv("DATA_DIR", "./data/raw"))
MODELS_DIR = Path(os.getenv("MODELS_DIR", "./data/models"))


def render(data: dict, master: pd.DataFrame, kpis: dict) -> None:
    render_hero(
        "زیرساخت و خط لوله داده",
        "وضعیت منابع داده، ETL، ذخیره‌سازی و سرویس‌های پلتفرم",
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("جداول بارگذاری‌شده", len(data))
    with c2:
        st.metric("رکوردهای کل", sum(len(df) for df in data.values()))
    with c3:
        model_files = list(MODELS_DIR.glob("*.joblib")) if MODELS_DIR.exists() else []
        st.metric("مدل‌های ML", len(model_files))
    with c4:
        st.metric("آخرین بروزرسانی", datetime.now().strftime("%H:%M"))

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
        ("پیش‌بینی بستری مجدد", True, "Gradient Boosting Classifier"),
        ("خوشه‌بندی بیماران", True, "K-Means بر اساس ویژگی‌های بالینی"),
        ("هشدارهای پیش‌بینی‌کننده", True, "آستانه‌بندی ریسک با سطح شدت"),
        ("کنترل دسترسی RBAC", True, "admin / clinician / researcher / viewer"),
        ("پردازش HL7", True, "پارسر پیام‌های HL7 v2.x"),
        ("متادیتای DICOM", True, "استخراج اطلاعات تصویربرداری"),
        ("پردازش جریانی Kafka", True, "رویدادهای admissions و alerts"),
        ("ذخیره‌سازی شیء MinIO", True, "فایل‌های خام DICOM/HL7"),
    ]

    for name, active, desc in features:
        icon = "✅" if active else "⏳"
        st.markdown(f"- {icon} **{name}** — {desc}")

    if not master.empty:
        st.markdown("### کیفیت داده")
        quality = {
            "بستری بدون بیمار": int(master["Patient_ID"].isna().sum()),
            "LOS منفی": int((master["Length_of_Stay"] < 0).sum()) if "Length_of_Stay" in master.columns else 0,
            "فیلدهای خالی Department": int(master["Department"].isna().sum()),
        }
        qdf = pd.DataFrame([{"بررسی": k, "تعداد": v, "وضعیت": "✅" if v == 0 else "⚠️"} for k, v in quality.items()])
        st.dataframe(qdf, use_container_width=True, hide_index=True)

    st.info("برای اجرای ETL و آموزش مدل از API یا دستورات `python -m barekat.etl.pipeline` و `python -m barekat.ml.pipeline` استفاده کنید.")
