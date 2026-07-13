"""Data ingestion from various health data sources."""

from pathlib import Path

import pandas as pd

from barekat.config.settings import get_settings


class CSVIngestor:
    """Load CSV health data files into DataFrames."""

    SUPPORTED_TABLES = (
        "patients", "admissions", "diagnoses", "medications", "lab_results",
        "clinical_notes", "vital_signs",
    )

    TABLE_DATE_COLUMNS: dict[str, tuple[str, ...]] = {
        "patients": (),
        "admissions": ("Admission_Date", "Discharge_Date"),
        "diagnoses": (),
        "medications": ("Prescribed_Date",),
        "lab_results": ("Test_Date",),
        "clinical_notes": ("Authored_At",),
        "vital_signs": ("Recorded_At",),
    }

    def __init__(self, data_dir: Path | None = None) -> None:
        settings = get_settings()
        self.data_dir = data_dir or Path(settings.data_raw_path)

    def load_table(self, table_name: str) -> pd.DataFrame:
        if table_name not in self.SUPPORTED_TABLES:
            raise ValueError(f"Unsupported table: {table_name}")

        file_path = self.data_dir / f"{table_name}.csv"
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        df = pd.read_csv(file_path)
        date_cols = [c for c in self.TABLE_DATE_COLUMNS.get(table_name, ()) if c in df.columns]
        if date_cols:
            df[date_cols] = df[date_cols].apply(pd.to_datetime, errors="coerce")
        return df

    def load_all(self) -> dict[str, pd.DataFrame]:
        return {
            table: self.load_table(table)
            for table in self.SUPPORTED_TABLES
            if (self.data_dir / f"{table}.csv").exists()
        }
