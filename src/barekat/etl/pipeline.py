"""Main ETL pipeline orchestrator with validation, logging, and incremental load."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import text

from barekat.config.settings import get_settings
from barekat.etl.incremental import (
    load_full_table,
    load_incremental,
    truncate_raw_tables,
)
from barekat.etl.run_logger import finish_run, start_run
from barekat.etl.transformers import DataTransformer
from barekat.etl.validation import validate_all
from barekat.ingestion.csv_loader import CSVIngestor
from barekat.storage.database import engine

TABLE_KEY_MAP = {
    "Patients": "patients",
    "Admissions": "admissions",
    "Diagnoses": "diagnoses",
    "Medications": "medications",
    "Lab_Results": "lab_results",
    "Admission_Summary": "admission_summary",
}


class ETLPipeline:
    """Extract, Transform, Load pipeline for health data."""

    CLEANERS = {
        "Patients": "clean_patients",
        "Admissions": "clean_admissions",
        "Diagnoses": "clean_diagnoses",
        "Medications": "clean_medications",
        "Lab_Results": "clean_lab_results",
    }

    def __init__(self) -> None:
        self.settings = get_settings()
        self.transformer = DataTransformer()
        self.ingestor = CSVIngestor(Path(self.settings.data_raw_path))

    def extract(self) -> dict[str, pd.DataFrame]:
        csv_tables = {
            "patients": "Patients",
            "admissions": "Admissions",
            "diagnoses": "Diagnoses",
            "medications": "Medications",
            "lab_results": "Lab_Results",
        }
        raw = self.ingestor.load_all()
        return {csv_tables[k]: v for k, v in raw.items()}

    def transform(self, data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        cleaned = {}
        for table_name, df in data.items():
            cleaner_name = self.CLEANERS.get(table_name)
            if cleaner_name is None:
                continue
            cleaner = getattr(self.transformer, cleaner_name)
            cleaned[table_name] = cleaner(df)
        if "Admissions" in data:
            cleaned["Admission_Summary"] = self.transformer.build_admission_summary(data)
        return cleaned

    def load(self, data: dict[str, pd.DataFrame], mode: str = "incremental") -> dict[str, int | dict]:
        counts: dict[str, int | dict] = {}
        load_order = ["Patients", "Admissions", "Diagnoses", "Medications", "Lab_Results", "Admission_Summary"]
        for table_name in load_order:
            if table_name not in data:
                continue
            table_key = TABLE_KEY_MAP[table_name]
            df = data[table_name]
            if mode == "full":
                counts[table_key] = load_full_table(df, table_key)
            else:
                counts[table_key] = load_incremental(df, table_key)
        return counts

    def run(
        self,
        mode: str = "incremental",
        *,
        run_id: int | None = None,
        celery_task_id: str | None = None,
        retry_count: int = 0,
        skip_validation: bool = False,
    ) -> dict:
        own_run = run_id is None
        if own_run:
            run_id = start_run(mode=mode, celery_task_id=celery_task_id, retry_count=retry_count)

        try:
            raw_data = self.extract()
            if not raw_data:
                raise ValueError("No source data found in CSV files")

            if self.settings.lake_enabled:
                try:
                    from barekat.lake.bronze_writer import BronzeWriter
                    BronzeWriter().land_etl_extract(raw_data)
                except Exception as exc:
                    print(f"Warning: bronze lake landing failed: {exc}")

            transformed = self.transform(raw_data)

            validation_result = {"success": True, "tables": {}}
            if not skip_validation:
                validation_result = validate_all(transformed)
                if not validation_result["success"]:
                    failed = [t for t, r in validation_result["tables"].items() if not r.get("success")]
                    raise ValueError(f"Great Expectations validation failed for: {', '.join(failed)}")

            if mode == "full":
                truncate_raw_tables()

            counts = self.load(transformed, mode=mode)
            quality = self.validate_data_quality()

            flat_counts = {
                k: v["total"] if isinstance(v, dict) else v
                for k, v in counts.items()
            }

            finish_run(
                run_id,
                status="success",
                records_loaded=flat_counts,
                validation_result=validation_result,
                quality_checks=quality,
            )
            return {
                "run_id": run_id,
                "mode": mode,
                "status": "success",
                "records_loaded": counts,
                "validation": validation_result,
                "quality_checks": quality,
            }

        except Exception as exc:
            finish_run(run_id, status="failed", error_message=str(exc))
            raise

    def validate_data_quality(self) -> dict[str, dict]:
        checks = {}
        with engine.connect() as conn:
            orphan_admissions = conn.execute(text("""
                SELECT COUNT(*) FROM raw.admissions a
                LEFT JOIN raw.patients p ON a.patient_id = p.patient_id
                WHERE p.patient_id IS NULL
            """)).scalar()
            checks["orphan_admissions"] = {"count": orphan_admissions, "passed": orphan_admissions == 0}

            future_dates = conn.execute(text("""
                SELECT COUNT(*) FROM raw.admissions
                WHERE admission_date > NOW()
            """)).scalar()
            checks["future_admission_dates"] = {"count": future_dates, "passed": future_dates == 0}

        return checks
