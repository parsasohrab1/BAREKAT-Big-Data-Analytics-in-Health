"""Bronze layer writer — land raw data to MinIO Data Lake."""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import pandas as pd
import structlog

from barekat.config.settings import get_settings
from barekat.lake import catalog, paths
from barekat.storage.minio_client import ObjectStorage

logger = structlog.get_logger(__name__)

BRONZE_TABLES = {
    "patients": "Patients",
    "admissions": "Admissions",
    "diagnoses": "Diagnoses",
    "medications": "Medications",
    "lab_results": "Lab_Results",
    "clinical_notes": "Clinical_Notes",
    "vital_signs": "Vital_Signs",
}


class BronzeWriter:
    """Write immutable raw snapshots to MinIO bronze layer."""

    def __init__(self, storage: ObjectStorage | None = None) -> None:
        self.storage = storage or ObjectStorage()
        self.bucket = get_settings().minio_bucket_lake

    def land_dataframe(
        self,
        table: str,
        df: pd.DataFrame,
        *,
        source: str = "csv",
        partition_dt: str | None = None,
    ) -> str:
        if df.empty:
            logger.info("bronze_skip_empty", table=table)
            return ""

        prefix = paths.bronze_path(table, source=source, partition_dt=partition_dt)
        filename = paths.partition_filename(table, "parquet")
        object_key = f"{prefix}/{filename}"

        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False, engine="pyarrow")
        buffer.seek(0)
        self.storage.upload_bytes(
            self.bucket,
            object_key,
            buffer.read(),
            content_type="application/octet-parquet",
        )

        catalog.register_table(
            paths.LAYER_BRONZE,
            table,
            prefix,
            fmt="parquet",
            row_count=len(df),
            metadata={"source": source, "partition": partition_dt or date.today().isoformat()},
        )
        logger.info("bronze_landed", table=table, rows=len(df), key=object_key)
        return object_key

    def land_csv_file(self, table: str, csv_path: Path, *, source: str = "csv") -> str:
        df = pd.read_csv(csv_path)
        return self.land_dataframe(table, df, source=source)

    def land_raw_bytes(
        self,
        table: str,
        data: bytes,
        filename: str,
        *,
        source: str = "ingest",
        content_type: str = "application/octet-stream",
    ) -> str:
        prefix = paths.bronze_path(table, source=source)
        object_key = f"{prefix}/{filename}"
        self.storage.upload_bytes(self.bucket, object_key, data, content_type=content_type)
        catalog.register_table(
            paths.LAYER_BRONZE,
            table,
            prefix,
            fmt="parquet",
            metadata={"source": source, "filename": filename},
        )
        return object_key

    def land_etl_extract(self, raw_data: dict[str, pd.DataFrame]) -> dict[str, str]:
        """Land ETL extract dict (PascalCase keys) to bronze."""
        mapping = {
            "Patients": "patients",
            "Admissions": "admissions",
            "Diagnoses": "diagnoses",
            "Medications": "medications",
            "Lab_Results": "lab_results",
            "Clinical_Notes": "clinical_notes",
            "Vital_Signs": "vital_signs",
        }
        results: dict[str, str] = {}
        for src_key, table in mapping.items():
            if src_key in raw_data and not raw_data[src_key].empty:
                results[table] = self.land_dataframe(table, raw_data[src_key])
        return results

    def list_bronze_objects(self, table: str, source: str = "csv") -> list[str]:
        prefix = f"{paths.bronze_path(table, source=source, partition_dt='')}".rsplit("dt=", 1)[0]
        return self.storage.list_objects(self.bucket, prefix=prefix)


def land_directory_to_bronze(data_dir: Path) -> dict[str, str]:
    """Land all CSV files from data/raw to bronze layer."""
    writer = BronzeWriter()
    results: dict[str, str] = {}
    for table, csv_name in BRONZE_TABLES.items():
        path = data_dir / f"{table}.csv"
        if not path.exists():
            alt = data_dir / f"{csv_name}.csv"
            path = alt if alt.exists() else path
        if path.exists():
            results[table] = writer.land_csv_file(table, path)
    return results
