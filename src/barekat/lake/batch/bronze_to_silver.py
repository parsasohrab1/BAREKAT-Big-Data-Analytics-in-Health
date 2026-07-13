"""Bronze → Silver batch job (Spark or pandas fallback)."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
import structlog

from barekat.config.settings import get_settings
from barekat.etl.transformers import DataTransformer
from barekat.lake import catalog, paths
from barekat.lake.spark_session import get_spark_session, write_table
from barekat.storage.minio_client import ObjectStorage

logger = structlog.get_logger(__name__)

SILVER_TABLES = ["patients", "admissions", "diagnoses", "medications", "lab_results"]

CLEANER_MAP = {
    "patients": ("Patients", "clean_patients"),
    "admissions": ("Admissions", "clean_admissions"),
    "diagnoses": ("Diagnoses", "clean_diagnoses"),
    "medications": ("Medications", "clean_medications"),
    "lab_results": ("Lab_Results", "clean_lab_results"),
}


def run_bronze_to_silver(tables: list[str] | None = None) -> dict[str, Any]:
    """Transform bronze parquet → silver curated tables with versioning."""
    tables = tables or SILVER_TABLES
    run_id = catalog.start_job("bronze_to_silver", layer=paths.LAYER_SILVER)

    try:
        settings = get_settings()
        if settings.lake_spark_enabled:
            result = _run_spark(tables)
        else:
            result = _run_pandas(tables)

        total = sum(result.get("rows", {}).values())
        catalog.finish_job(
            run_id,
            status="success",
            records_processed=total,
            tables_processed=list(result.get("rows", {}).keys()),
        )
        return {"status": "success", "run_id": run_id, **result}
    except Exception as exc:
        catalog.finish_job(run_id, status="failed", error_message=str(exc))
        raise


def _run_pandas(tables: list[str]) -> dict[str, Any]:
    """Pandas fallback — reads latest bronze parquet from MinIO, writes silver parquet."""
    settings = get_settings()
    storage = ObjectStorage()
    transformer = DataTransformer()
    bucket = settings.minio_bucket_lake
    fmt = settings.lake_table_format
    rows: dict[str, int] = {}

    for table in tables:
        objects = storage.list_objects(bucket, prefix=f"bronze/csv/{table}/")
        if not objects:
            logger.warning("bronze_missing", table=table)
            continue

        latest = sorted(objects)[-1]
        stream = storage.get_object_stream(bucket, latest)
        df = pd.read_parquet(io.BytesIO(stream.read()))
        stream.close()

        pascal, cleaner_name = CLEANER_MAP[table]
        cleaner = getattr(transformer, cleaner_name)
        silver_df = cleaner(df)

        buffer = io.BytesIO()
        silver_df.to_parquet(buffer, index=False, engine="pyarrow")
        buffer.seek(0)

        silver_key = f"{paths.silver_path(table)}/data.parquet"
        storage.upload_bytes(bucket, silver_key, buffer.read(), content_type="application/octet-parquet")

        catalog.register_table(
            paths.LAYER_SILVER,
            table,
            paths.silver_path(table),
            fmt=fmt if fmt != "delta" else "parquet",
            row_count=len(silver_df),
            metadata={"engine": "pandas", "bronze_source": latest},
        )
        rows[table] = len(silver_df)
        logger.info("silver_written", table=table, rows=len(silver_df))

    return {"engine": "pandas", "rows": rows}


def _run_spark(tables: list[str]) -> dict[str, Any]:
    """Spark batch with Delta/Iceberg versioning on MinIO."""
    settings = get_settings()
    spark = get_spark_session("barekat-bronze-to-silver")
    transformer = DataTransformer()
    rows: dict[str, int] = {}

    for table in tables:
        bronze_uri = paths.s3a_uri(f"bronze/csv/{table}/")
        try:
            bronze_df = spark.read.parquet(bronze_uri)
        except Exception:
            logger.warning("spark_bronze_empty", table=table, uri=bronze_uri)
            continue

        pdf = bronze_df.toPandas()
        pascal, cleaner_name = CLEANER_MAP[table]
        cleaner = getattr(transformer, cleaner_name)
        silver_pdf = cleaner(pdf)
        silver_df = spark.createDataFrame(silver_pdf)

        silver_uri = paths.s3a_uri(paths.silver_path(table))
        write_table(silver_df, silver_uri, mode="overwrite")

        count = silver_df.count()
        catalog.register_table(
            paths.LAYER_SILVER,
            table,
            paths.silver_path(table),
            fmt=settings.lake_table_format,
            row_count=count,
            metadata={"engine": "spark"},
        )
        rows[table] = count

    spark.stop()
    return {"engine": "spark", "rows": rows}
