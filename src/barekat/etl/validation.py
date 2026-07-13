"""Great Expectations schema validation for ETL data."""

from __future__ import annotations

import pandas as pd

try:
    import great_expectations as ge
except ImportError:  # pragma: no cover
    ge = None


def _apply_patients_expectations(gdf) -> None:
    gdf.expect_table_columns_to_match_ordered_list([
        "patient_id", "age", "gender", "blood_type", "bmi",
        "smoking_status", "diabetes", "hypertension",
    ])
    gdf.expect_column_values_to_not_be_null("patient_id")
    gdf.expect_column_values_to_be_unique("patient_id")
    gdf.expect_column_values_to_be_between("age", min_value=0, max_value=150)
    gdf.expect_column_values_to_be_in_set("gender", value_set=["M", "F", "O"], mostly=0.95)


def _apply_admissions_expectations(gdf) -> None:
    gdf.expect_column_values_to_not_be_null("admission_id")
    gdf.expect_column_values_to_not_be_null("patient_id")
    gdf.expect_column_values_to_be_unique("admission_id")
    gdf.expect_column_values_to_be_between("length_of_stay", min_value=0, max_value=365, mostly=0.99)


def _apply_diagnoses_expectations(gdf) -> None:
    gdf.expect_column_values_to_not_be_null("diagnosis_id")
    gdf.expect_column_values_to_not_be_null("admission_id")
    gdf.expect_column_values_to_not_be_null("icd_code")
    gdf.expect_column_values_to_be_unique("diagnosis_id")


def _apply_medications_expectations(gdf) -> None:
    gdf.expect_column_values_to_not_be_null("medication_id")
    gdf.expect_column_values_to_not_be_null("admission_id")
    gdf.expect_column_values_to_be_unique("medication_id")


def _apply_lab_results_expectations(gdf) -> None:
    gdf.expect_column_values_to_not_be_null("lab_id")
    gdf.expect_column_values_to_not_be_null("admission_id")
    gdf.expect_column_values_to_be_unique("lab_id")


def _validate_with_ge(df: pd.DataFrame, apply_fn) -> dict:
    if ge is None:
        return {"success": False, "error": "great_expectations not installed", "statistics": {}}
    if df.empty:
        return {"success": True, "statistics": {"evaluated_expectations": 0}, "results": []}

    gdf = ge.from_pandas(df)
    apply_fn(gdf)
    result = gdf.validate(result_format="SUMMARY")
    return {
        "success": result["success"],
        "statistics": result.get("statistics", {}),
        "results": [
            {
                "expectation_type": r.expectation_config.expectation_type,
                "success": r.success,
                "column": r.expectation_config.kwargs.get("column"),
            }
            for r in result.results
        ],
    }


def validate_table(df: pd.DataFrame, table_name: str) -> dict:
    apply_fn = {
        "Patients": _apply_patients_expectations,
        "Admissions": _apply_admissions_expectations,
        "Diagnoses": _apply_diagnoses_expectations,
        "Medications": _apply_medications_expectations,
        "Lab_Results": _apply_lab_results_expectations,
    }.get(table_name)

    if apply_fn is None:
        return {"success": True, "statistics": {}, "results": [], "skipped": True}

    return _validate_with_ge(df, apply_fn)


def validate_all(data: dict[str, pd.DataFrame]) -> dict:
    results = {}
    all_passed = True
    for table_name, df in data.items():
        if table_name == "Admission_Summary":
            continue
        result = validate_table(df, table_name)
        results[table_name] = result
        if not result.get("success", False):
            all_passed = False
    return {"success": all_passed, "tables": results}
