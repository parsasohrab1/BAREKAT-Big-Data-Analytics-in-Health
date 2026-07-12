"""Main ETL pipeline orchestrator."""

from pathlib import Path

import pandas as pd
from sqlalchemy import text

from barekat.config.settings import get_settings
from barekat.etl.transformers import DataTransformer
from barekat.ingestion.csv_loader import CSVIngestor
from barekat.storage.database import engine


class ETLPipeline:
  """Extract, Transform, Load pipeline for health data."""

  RAW_TABLES = {
    "Patients": "raw.patients",
    "Admissions": "raw.admissions",
    "Diagnoses": "raw.diagnoses",
    "Medications": "raw.medications",
    "Lab_Results": "raw.lab_results",
  }

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
      cleaner_name = self.CLEANERS[table_name]
      cleaner = getattr(self.transformer, cleaner_name)
      cleaned[table_name] = cleaner(df)
    cleaned["Admission_Summary"] = self.transformer.build_admission_summary(data)
    return cleaned

  def load(self, data: dict[str, pd.DataFrame], if_exists: str = "append") -> dict[str, int]:
    counts = {}
    for table_name, df in data.items():
      if table_name == "Admission_Summary":
        df.to_sql("admission_summary", engine, schema="analytics", if_exists=if_exists, index=False)
        counts["admission_summary"] = len(df)
        continue

      db_table = self.RAW_TABLES[table_name]
      schema, table = db_table.split(".")
      df.to_sql(table, engine, schema=schema, if_exists=if_exists, index=False)
      counts[table] = len(df)
    return counts

  def run(self, if_exists: str = "replace") -> dict[str, int]:
    print("ETL: Extracting data...")
    raw_data = self.extract()
    print(f"ETL: Extracted {len(raw_data)} tables")

    print("ETL: Transforming data...")
    transformed = self.transform(raw_data)

    print("ETL: Loading to database...")
    counts = self.load(transformed, if_exists=if_exists)
    print(f"ETL: Loaded {sum(counts.values())} total records")
    return counts

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
