"""Tests for Data Lake medallion architecture."""

from unittest.mock import MagicMock, patch

import pandas as pd

from barekat.lake.paths import bronze_path, gold_path, lake_bucket, silver_path, s3a_uri


def test_bronze_path_partition():
    path = bronze_path("patients", source="csv", partition_dt="2026-07-01")
    assert path == "bronze/csv/patients/dt=2026-07-01"


def test_silver_gold_paths():
    assert silver_path("admissions") == "silver/health/admissions"
    assert gold_path("marts", "admission_summary") == "gold/marts/admission_summary"


def test_s3a_uri():
    uri = s3a_uri("bronze/csv/patients/")
    assert uri.startswith("s3a://")
    assert "bronze/csv/patients" in uri


@patch("barekat.lake.bronze_writer.catalog.register_table")
@patch("barekat.lake.bronze_writer.ObjectStorage")
def test_bronze_writer_lands_parquet(mock_storage_cls, mock_register):
    mock_storage = MagicMock()
    mock_storage_cls.return_value = mock_storage

    from barekat.lake.bronze_writer import BronzeWriter

    df = pd.DataFrame({"Patient_ID": ["P1"], "Age": [45]})
    writer = BronzeWriter(storage=mock_storage)
    key = writer.land_dataframe("patients", df, partition_dt="2026-07-01")

    assert key.endswith(".parquet")
    mock_storage.upload_bytes.assert_called_once()
    mock_register.assert_called_once()


def test_lake_bucket_default():
    assert lake_bucket()  # non-empty string
