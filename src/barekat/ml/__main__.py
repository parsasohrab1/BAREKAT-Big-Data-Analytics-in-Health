"""ML pipeline CLI entry point."""

from pathlib import Path

from barekat.config.settings import get_settings
from barekat.ingestion.csv_loader import CSVIngestor
from barekat.ml.pipeline import MLPipeline


def main():
    settings = get_settings()
    ingestor = CSVIngestor(Path(settings.data_raw_path))
    raw = ingestor.load_all()

    table_map = {
        "patients": "Patients",
        "admissions": "Admissions",
        "diagnoses": "Diagnoses",
        "medications": "Medications",
        "lab_results": "Lab_Results",
    }
    data = {table_map[k]: v for k, v in raw.items()}

    ml = MLPipeline()
    results = ml.run_all(data)
    print(f"ML training results: {results}")


if __name__ == "__main__":
    main()
