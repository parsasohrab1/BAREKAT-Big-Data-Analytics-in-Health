"""DICOM metadata models and extraction."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class DICOMMetadata:
    patient_id: str = ""
    study_uid: str = ""
    series_uid: str = ""
    sop_instance_uid: str = ""
    modality: str = ""
    study_date: str = ""
    body_part: str = ""
    study_description: str = ""
    series_description: str = ""
    instance_number: int = 1
    rows: int = 0
    columns: int = 0
    file_path: str = ""
    storage_path: str = ""
    thumbnail_path: str = ""
    pacs_source: str = "local"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_metadata(file_path: Path, *, read_pixels: bool = False) -> DICOMMetadata:
    """Extract metadata from a DICOM file."""
    try:
        import pydicom

        ds = pydicom.dcmread(str(file_path), stop_before_pixels=not read_pixels)
        return DICOMMetadata(
            patient_id=str(getattr(ds, "PatientID", "")),
            study_uid=str(getattr(ds, "StudyInstanceUID", "")),
            series_uid=str(getattr(ds, "SeriesInstanceUID", "")),
            sop_instance_uid=str(getattr(ds, "SOPInstanceUID", "")),
            modality=str(getattr(ds, "Modality", "")),
            study_date=str(getattr(ds, "StudyDate", "")),
            body_part=str(getattr(ds, "BodyPartExamined", "")),
            study_description=str(getattr(ds, "StudyDescription", "")),
            series_description=str(getattr(ds, "SeriesDescription", "")),
            instance_number=int(getattr(ds, "InstanceNumber", 1) or 1),
            rows=int(getattr(ds, "Rows", 0) or 0),
            columns=int(getattr(ds, "Columns", 0) or 0),
            file_path=str(file_path),
        )
    except ImportError:
        return DICOMMetadata(file_path=str(file_path))
    except Exception:
        return DICOMMetadata(file_path=str(file_path))


def scan_directory(directory: Path) -> list[DICOMMetadata]:
    results = []
    for path in sorted(directory.rglob("*.dcm")):
        meta = extract_metadata(path)
        if meta.study_uid:
            results.append(meta)
    return results
