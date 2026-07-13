"""Dashboard helpers for DICOM imaging."""

from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

import pandas as pd


def load_imaging_studies() -> pd.DataFrame:
    """Load DICOM study catalog from PostgreSQL or local directory."""
    try:
        from barekat.imaging.store import list_studies
        df = list_studies(limit=100)
        if not df.empty:
            return df
    except Exception:
        pass

    return _scan_local_dicom()


def _scan_local_dicom() -> pd.DataFrame:
    from barekat.imaging.metadata import scan_directory

    base = Path(os.getenv("DICOM_DATA_PATH", "./data/dicom"))
    if not base.exists():
        return pd.DataFrame()

    records = []
    for meta in scan_directory(base):
        records.append({
            "study_uid": meta.study_uid,
            "patient_id": meta.patient_id,
            "modality": meta.modality,
            "study_date": meta.study_date,
            "body_part": meta.body_part,
            "study_description": meta.study_description,
            "file_path": meta.file_path,
            "pacs_source": "local",
        })
    return pd.DataFrame(records)


def get_local_thumbnail(file_path: str) -> bytes | None:
    try:
        from barekat.imaging.thumbnail import generate_thumbnail
        return generate_thumbnail(Path(file_path))
    except Exception:
        return None


def get_local_viewer_image(file_path: str, window: float, level: float) -> bytes | None:
    try:
        from barekat.imaging.thumbnail import render_png_bytes
        return render_png_bytes(Path(file_path), window=window, level=level)
    except Exception:
        return None


def bytes_to_image(bytes_data: bytes):
    from PIL import Image
    return Image.open(BytesIO(bytes_data))
