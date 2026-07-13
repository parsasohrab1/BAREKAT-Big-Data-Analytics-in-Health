"""DICOM study persistence — MinIO + PostgreSQL."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text

from barekat.config.settings import get_settings
from barekat.imaging.metadata import DICOMMetadata, extract_metadata
from barekat.imaging.thumbnail import generate_thumbnail
from barekat.storage.database import engine
from barekat.storage.minio_client import ObjectStorage


def _thumbnail_object_key(study_uid: str) -> str:
    return f"dicom-thumbnails/{study_uid}.png"


def _dicom_object_key(study_uid: str, filename: str) -> str:
    return f"dicom/{study_uid}/{filename}"


def ingest_dicom_file(file_path: Path, *, pacs_source: str = "local") -> DICOMMetadata | None:
    """Upload DICOM to MinIO, generate thumbnail, persist metadata."""
    meta = extract_metadata(file_path)
    if not meta.study_uid:
        return None

    meta.pacs_source = pacs_source
    storage = ObjectStorage()
    settings = get_settings()

    dicom_key = _dicom_object_key(meta.study_uid, file_path.name)
    storage.upload_file(settings.minio_bucket_raw, dicom_key, file_path)
    meta.storage_path = dicom_key

    try:
        thumb_bytes = generate_thumbnail(file_path)
        thumb_key = _thumbnail_object_key(meta.study_uid)
        storage.upload_bytes(settings.minio_bucket_processed, thumb_key, thumb_bytes, "image/png")
        meta.thumbnail_path = thumb_key
    except Exception:
        meta.thumbnail_path = ""

    _upsert_study_record(meta)
    return meta


def ingest_directory(directory: Path, *, pacs_source: str = "local") -> list[DICOMMetadata]:
    ingested = []
    for path in sorted(directory.rglob("*.dcm")):
        meta = ingest_dicom_file(path, pacs_source=pacs_source)
        if meta:
            ingested.append(meta)
    return ingested


def _upsert_study_record(meta: DICOMMetadata) -> None:
    sql = text("""
        INSERT INTO raw.dicom_studies (
            study_uid, series_uid, patient_id, modality, study_date, body_part,
            study_description, instance_count, storage_path, thumbnail_path, pacs_source
        ) VALUES (
            :study_uid, :series_uid, :patient_id, :modality, :study_date, :body_part,
            :study_description, 1, :storage_path, :thumbnail_path, :pacs_source
        )
        ON CONFLICT (study_uid) DO UPDATE SET
            thumbnail_path = EXCLUDED.thumbnail_path,
            storage_path = EXCLUDED.storage_path,
            instance_count = raw.dicom_studies.instance_count + 1,
            retrieved_at = NOW()
    """)
    with engine.begin() as conn:
        conn.execute(sql, {
            "study_uid": meta.study_uid,
            "series_uid": meta.series_uid or None,
            "patient_id": meta.patient_id or None,
            "modality": meta.modality or None,
            "study_date": _parse_study_date(meta.study_date),
            "body_part": meta.body_part or None,
            "study_description": meta.study_description or None,
            "storage_path": meta.storage_path or None,
            "thumbnail_path": meta.thumbnail_path or None,
            "pacs_source": meta.pacs_source,
        })


def _parse_study_date(value: str) -> str | None:
    if not value or len(value) < 8:
        return None
    return f"{value[:4]}-{value[4:6]}-{value[6:8]}"


def list_studies(limit: int = 100, modality: str | None = None) -> pd.DataFrame:
    query = """
        SELECT study_id, study_uid, patient_id, modality, study_date, body_part,
               study_description, instance_count, thumbnail_path, pacs_source, retrieved_at
        FROM raw.dicom_studies
    """
    params: dict[str, Any] = {"limit": limit}
    if modality:
        query += " WHERE modality ILIKE :modality"
        params["modality"] = f"%{modality}%"
    query += " ORDER BY retrieved_at DESC LIMIT :limit"

    with engine.connect() as conn:
        rows = conn.execute(text(query), params).mappings().all()
    return pd.DataFrame([dict(r) for r in rows])


def get_study_by_uid(study_uid: str) -> dict[str, Any] | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM raw.dicom_studies WHERE study_uid = :uid"),
            {"uid": study_uid},
        ).mappings().first()
    return dict(row) if row else None


def get_thumbnail_bytes(study_uid: str) -> bytes | None:
    study = get_study_by_uid(study_uid)
    if not study or not study.get("thumbnail_path"):
        return None
    settings = get_settings()
    storage = ObjectStorage()
    try:
        response = storage.get_object_stream(settings.minio_bucket_processed, study["thumbnail_path"])
        return response.read()
    except Exception:
        return None


def get_viewer_file_path(study_uid: str) -> Path | None:
    """Resolve local or downloaded DICOM path for viewer rendering."""
    study = get_study_by_uid(study_uid)
    if not study or not study.get("storage_path"):
        return None
    settings = get_settings()
    local_cache = Path(settings.data_raw_path) / "dicom_cache" / study_uid
    local_cache.mkdir(parents=True, exist_ok=True)
    cached = list(local_cache.glob("*.dcm"))
    if cached:
        return cached[0]

    storage = ObjectStorage()
    dest = local_cache / "instance.dcm"
    try:
        storage.download_file(settings.minio_bucket_raw, study["storage_path"], dest)
        return dest
    except Exception:
        return None
