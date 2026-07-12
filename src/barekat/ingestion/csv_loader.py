"""Data ingestion from various health data sources."""

from pathlib import Path

import pandas as pd

from barekat.config.settings import get_settings


class CSVIngestor:
    """Load CSV health data files into DataFrames."""

    SUPPORTED_TABLES = ("patients", "admissions", "diagnoses", "medications", "lab_results")

    DATE_COLUMNS = ["Admission_Date", "Discharge_Date", "Prescribed_Date", "Test_Date"]

    def __init__(self, data_dir: Path | None = None) -> None:
        settings = get_settings()
        self.data_dir = data_dir or Path(settings.data_raw_path)

    def load_table(self, table_name: str) -> pd.DataFrame:
        if table_name not in self.SUPPORTED_TABLES:
            raise ValueError(f"Unsupported table: {table_name}")

        file_path = self.data_dir / f"{table_name}.csv"
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        return pd.read_csv(file_path, parse_dates=self.DATE_COLUMNS)

    def load_all(self) -> dict[str, pd.DataFrame]:
        return {
            table: self.load_table(table)
            for table in self.SUPPORTED_TABLES
            if (self.data_dir / f"{table}.csv").exists()
        }
