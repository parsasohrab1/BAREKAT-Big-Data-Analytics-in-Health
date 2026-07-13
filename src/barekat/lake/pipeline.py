"""Data Lake pipeline orchestrator — Bronze → Silver → Gold."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from barekat.config.settings import get_settings
from barekat.lake.batch.bronze_to_silver import run_bronze_to_silver
from barekat.lake.batch.silver_to_gold import run_silver_to_gold
from barekat.lake.bronze_writer import BronzeWriter, land_directory_to_bronze
from barekat.lake import catalog

logger = structlog.get_logger(__name__)


class LakePipeline:
    """Medallion pipeline on MinIO with optional Spark + Delta/Iceberg."""

    def run_full(self, *, land_csv: bool = True) -> dict[str, Any]:
        results: dict[str, Any] = {"steps": []}

        if land_csv:
            data_path = Path(get_settings().data_raw_path)
            bronze_result = land_directory_to_bronze(data_path)
            results["bronze"] = bronze_result
            results["steps"].append("bronze_land")

        silver_result = run_bronze_to_silver()
        results["silver"] = silver_result
        results["steps"].append("bronze_to_silver")

        gold_result = run_silver_to_gold()
        results["gold"] = gold_result
        results["steps"].append("silver_to_gold")

        results["status"] = "success"
        logger.info("lake_pipeline_completed", steps=results["steps"])
        return results

    def run_incremental(self, raw_data: dict | None = None) -> dict[str, Any]:
        """Land new extract to bronze, then refresh silver/gold."""
        results: dict[str, Any] = {"steps": []}

        if raw_data:
            writer = BronzeWriter()
            results["bronze"] = writer.land_etl_extract(raw_data)
            results["steps"].append("bronze_land")

        results["silver"] = run_bronze_to_silver()
        results["steps"].append("bronze_to_silver")
        results["gold"] = run_silver_to_gold()
        results["steps"].append("silver_to_gold")
        results["status"] = "success"
        return results

    def status(self) -> dict[str, Any]:
        settings = get_settings()
        return {
            "bucket": settings.minio_bucket_lake,
            "table_format": settings.lake_table_format,
            "spark_enabled": settings.lake_spark_enabled,
            "tables": catalog.list_tables(),
            "recent_jobs": catalog.recent_jobs(limit=10),
        }
