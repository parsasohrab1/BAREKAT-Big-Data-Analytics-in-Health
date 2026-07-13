"""Silver → Gold batch job — curated marts for analytics."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
import structlog

from barekat.config.settings import get_settings
from barekat.lake import catalog, paths
from barekat.lake.spark_session import get_spark_session, write_table
from barekat.storage.minio_client import ObjectStorage

logger = structlog.get_logger(__name__)


def run_silver_to_gold() -> dict[str, Any]:
    """Build gold marts: admission_summary, department_stats, alert_rollup."""
    run_id = catalog.start_job("silver_to_gold", layer=paths.LAYER_GOLD)

    try:
        settings = get_settings()
        if settings.lake_spark_enabled:
            result = _run_spark()
        else:
            result = _run_pandas()

        total = sum(result.get("rows", {}).values())
        catalog.finish_job(
            run_id,
            status="success",
            records_processed=total,
            tables_processed=list(result.get("marts", [])),
        )
        return {"status": "success", "run_id": run_id, **result}
    except Exception as exc:
        catalog.finish_job(run_id, status="failed", error_message=str(exc))
        raise


def _load_silver_table(storage: ObjectStorage, bucket: str, table: str) -> pd.DataFrame:
    key = f"{paths.silver_path(table)}/data.parquet"
    try:
        stream = storage.get_object_stream(bucket, key)
        df = pd.read_parquet(io.BytesIO(stream.read()))
        stream.close()
        return df
    except Exception:
        return pd.DataFrame()


def _build_gold_marts(
    admissions: pd.DataFrame,
    diagnoses: pd.DataFrame,
    medications: pd.DataFrame | None = None,
    lab_results: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    marts: dict[str, pd.DataFrame] = {}
    if admissions.empty:
        return marts

    summary = admissions[["admission_id", "patient_id", "department", "length_of_stay"]].copy()
    if not diagnoses.empty:
        diag_counts = diagnoses.groupby("admission_id").size().reset_index(name="diagnosis_count")
        summary = summary.merge(diag_counts, on="admission_id", how="left")
    if medications is not None and not medications.empty:
        med_counts = medications.groupby("admission_id").size().reset_index(name="medication_count")
        summary = summary.merge(med_counts, on="admission_id", how="left")
    if lab_results is not None and not lab_results.empty:
        lab_counts = lab_results.groupby("admission_id").size().reset_index(name="lab_test_count")
        summary = summary.merge(lab_counts, on="admission_id", how="left")
    marts["admission_summary"] = summary.fillna(0)

    marts["department_stats"] = (
        admissions.groupby("department")
        .agg(
            admission_count=("admission_id", "count"),
            avg_los=("length_of_stay", "mean"),
            readmission_rate=("readmission_flag", "mean"),
        )
        .reset_index()
    )

    try:
        from barekat.services.alerts import load_active_alerts
        alerts = load_active_alerts(limit=5000)
        if not alerts.empty:
            marts["alert_rollup"] = (
                alerts.groupby(["severity", "alert_type"])
                .size()
                .reset_index(name="count")
            )
    except Exception:
        marts["alert_rollup"] = pd.DataFrame()

    return marts


def _run_pandas() -> dict[str, Any]:
    settings = get_settings()
    storage = ObjectStorage()
    bucket = settings.minio_bucket_lake

    admissions = _load_silver_table(storage, bucket, "admissions")
    diagnoses = _load_silver_table(storage, bucket, "diagnoses")
    medications = _load_silver_table(storage, bucket, "medications")
    lab_results = _load_silver_table(storage, bucket, "lab_results")
    marts = _build_gold_marts(admissions, diagnoses, medications, lab_results)

    rows: dict[str, int] = {}
    for mart_name, df in marts.items():
        if df.empty:
            continue
        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False, engine="pyarrow")
        buffer.seek(0)
        gold_key = f"{paths.gold_path('marts', mart_name)}/data.parquet"
        storage.upload_bytes(bucket, gold_key, buffer.read(), content_type="application/octet-parquet")
        catalog.register_table(
            paths.LAYER_GOLD,
            mart_name,
            paths.gold_path("marts", mart_name),
            fmt="parquet",
            row_count=len(df),
            metadata={"engine": "pandas"},
        )
        rows[mart_name] = len(df)

    return {"engine": "pandas", "marts": list(rows.keys()), "rows": rows}


def _run_spark() -> dict[str, Any]:
    settings = get_settings()
    spark = get_spark_session("barekat-silver-to-gold")
    storage = ObjectStorage()
    bucket = settings.minio_bucket_lake

    admissions = _load_silver_table(storage, bucket, "admissions")
    diagnoses = _load_silver_table(storage, bucket, "diagnoses")
    medications = _load_silver_table(storage, bucket, "medications")
    lab_results = _load_silver_table(storage, bucket, "lab_results")
    marts = _build_gold_marts(admissions, diagnoses, medications, lab_results)

    rows: dict[str, int] = {}
    for mart_name, pdf in marts.items():
        if pdf.empty:
            continue
        gold_uri = paths.s3a_uri(paths.gold_path("marts", mart_name))
        gold_df = spark.createDataFrame(pdf)
        write_table(gold_df, gold_uri, mode="overwrite")
        count = gold_df.count()
        catalog.register_table(
            paths.LAYER_GOLD,
            mart_name,
            paths.gold_path("marts", mart_name),
            fmt=settings.lake_table_format,
            row_count=count,
            metadata={"engine": "spark"},
        )
        rows[mart_name] = count

    spark.stop()
    return {"engine": "spark", "marts": list(rows.keys()), "rows": rows}
