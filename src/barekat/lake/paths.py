"""Medallion lake path conventions for MinIO (Bronze / Silver / Gold)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from barekat.config.settings import get_settings

LAYER_BRONZE = "bronze"
LAYER_SILVER = "silver"
LAYER_GOLD = "gold"


def _today() -> str:
    return date.today().isoformat()


def lake_bucket() -> str:
    return get_settings().minio_bucket_lake


def bronze_path(table: str, source: str = "csv", partition_dt: str | None = None) -> str:
    """Object prefix: bronze/{source}/{table}/dt=YYYY-MM-DD/"""
    dt = partition_dt or _today()
    settings = get_settings()
    return f"{settings.lake_bronze_prefix}/{source}/{table}/dt={dt}"


def silver_path(table: str) -> str:
    settings = get_settings()
    return f"{settings.lake_silver_prefix}/health/{table}"


def gold_path(mart: str, table: str) -> str:
    settings = get_settings()
    return f"{settings.lake_gold_prefix}/{mart}/{table}"


def s3a_uri(key: str, bucket: str | None = None) -> str:
    b = bucket or lake_bucket()
    return f"s3a://{b}/{key}"


def partition_filename(table: str, suffix: str = "parquet") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{table}_{ts}.{suffix}"


def stream_bronze_path() -> str:
    settings = get_settings()
    return f"{settings.lake_bronze_prefix}/stream/events"
