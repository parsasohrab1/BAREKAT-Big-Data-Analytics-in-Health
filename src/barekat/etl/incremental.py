"""Incremental load helpers with upsert and watermarks."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from barekat.storage.database import engine

TABLE_CONFIG = {
    "patients": {"schema": "raw", "pk": "patient_id"},
    "admissions": {"schema": "raw", "pk": "admission_id"},
    "diagnoses": {"schema": "raw", "pk": "diagnosis_id"},
    "medications": {"schema": "raw", "pk": "medication_id"},
    "lab_results": {"schema": "raw", "pk": "lab_id"},
    "admission_summary": {"schema": "analytics", "pk": "admission_id"},
}

LOAD_ORDER = ["patients", "admissions", "diagnoses", "medications", "lab_results", "admission_summary"]


def get_existing_ids(schema: str, table: str, pk: str) -> set:
    query = text(f"SELECT {pk} FROM {schema}.{table}")
    try:
        with engine.connect() as conn:
            rows = conn.execute(query).fetchall()
        return {row[0] for row in rows}
    except Exception:
        return set()


def split_new_and_updated(df: pd.DataFrame, pk: str, existing_ids: set) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty or pk not in df.columns:
        return df, pd.DataFrame()
    new_df = df[~df[pk].isin(existing_ids)].copy()
    update_df = df[df[pk].isin(existing_ids)].copy()
    return new_df, update_df


def upsert_dataframe(df: pd.DataFrame, schema: str, table: str, pk: str) -> int:
    """PostgreSQL INSERT ... ON CONFLICT DO UPDATE."""
    if df.empty:
        return 0

    columns = list(df.columns)
    col_list = ", ".join(columns)
    placeholders = ", ".join(f":{col}" for col in columns)
    update_cols = [c for c in columns if c not in (pk, "created_at")]
    update_clause = ", ".join(f"{col} = EXCLUDED.{col}" for col in update_cols)

    sql = f"""
        INSERT INTO {schema}.{table} ({col_list})
        VALUES ({placeholders})
        ON CONFLICT ({pk}) DO UPDATE SET {update_clause}
    """
    records = df.where(pd.notnull(df), None).to_dict(orient="records")
    with engine.begin() as conn:
        for record in records:
            conn.execute(text(sql), record)
    return len(records)


def append_new_only(df: pd.DataFrame, schema: str, table: str, pk: str) -> int:
    existing = get_existing_ids(schema, table, pk)
    new_df, _ = split_new_and_updated(df, pk, existing)
    if new_df.empty:
        return 0
    new_df.to_sql(table, engine, schema=schema, if_exists="append", index=False)
    return len(new_df)


def load_incremental(df: pd.DataFrame, table_key: str) -> dict[str, int]:
    config = TABLE_CONFIG[table_key]
    schema, pk = config["schema"], config["pk"]
    existing = get_existing_ids(schema, table_key, pk)
    new_df, update_df = split_new_and_updated(df, pk, existing)

    inserted = 0
    updated = 0
    if not new_df.empty:
        new_df.to_sql(table_key, engine, schema=schema, if_exists="append", index=False)
        inserted = len(new_df)
    if not update_df.empty:
        updated = upsert_dataframe(update_df, schema, table_key, pk)

    update_watermark(table_key, df, pk, inserted + updated)
    return {"inserted": inserted, "updated": updated, "total": inserted + updated}


def load_full_table(df: pd.DataFrame, table_key: str) -> int:
    config = TABLE_CONFIG[table_key]
    schema = config["schema"]
    pk = config["pk"]

    if df.empty:
        return 0

    upsert_dataframe(df, schema, table_key, pk)
    update_watermark(table_key, df, pk, len(df))
    return len(df)


def truncate_raw_tables() -> None:
    sql = """
        TRUNCATE TABLE
            analytics.admission_summary,
            raw.lab_results,
            raw.medications,
            raw.diagnoses,
            raw.admissions,
            raw.patients
        CASCADE
    """
    with engine.begin() as conn:
        conn.execute(text(sql))


def update_watermark(table_name: str, df: pd.DataFrame, pk: str, count: int) -> None:
    last_id = None
    if not df.empty and pk in df.columns:
        last_id = str(df[pk].iloc[-1])

    query = text("""
        INSERT INTO staging.etl_watermarks (table_name, last_loaded_at, last_record_id, record_count)
        VALUES (:table_name, NOW(), :last_record_id, :record_count)
        ON CONFLICT (table_name) DO UPDATE SET
            last_loaded_at = NOW(),
            last_record_id = EXCLUDED.last_record_id,
            record_count = staging.etl_watermarks.record_count + EXCLUDED.record_count
    """)
    with engine.begin() as conn:
        conn.execute(query, {
            "table_name": table_name,
            "last_record_id": last_id,
            "record_count": count,
        })
