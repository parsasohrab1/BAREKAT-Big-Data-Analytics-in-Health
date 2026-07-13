"""Tests for incremental ETL helpers."""

import pandas as pd

from barekat.etl.incremental import split_new_and_updated


def test_split_new_and_updated():
    df = pd.DataFrame({
        "patient_id": ["PT001", "PT002", "PT003"],
        "age": [30, 40, 50],
    })
    existing = {"PT001", "PT002"}
    new_df, update_df = split_new_and_updated(df, "patient_id", existing)
    assert len(new_df) == 1
    assert new_df.iloc[0]["patient_id"] == "PT003"
    assert len(update_df) == 2
