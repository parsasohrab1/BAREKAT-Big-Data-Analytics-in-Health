"""DICOM metadata extractor (lightweight, no pixel data processing)."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class DICOMMetadata:
  patient_id: str = ""
  study_uid: str = ""
  series_uid: str = ""
  modality: str = ""
  study_date: str = ""
  body_part: str = ""
  file_path: str = ""


class DICOMLoader:
  """Extract metadata from DICOM files. Requires pydicom for full parsing."""

  def extract_metadata(self, file_path: Path) -> DICOMMetadata:
    try:
      import pydicom  # optional dependency

      ds = pydicom.dcmread(str(file_path), stop_before_pixels=True)
      return DICOMMetadata(
        patient_id=str(getattr(ds, "PatientID", "")),
        study_uid=str(getattr(ds, "StudyInstanceUID", "")),
        series_uid=str(getattr(ds, "SeriesInstanceUID", "")),
        modality=str(getattr(ds, "Modality", "")),
        study_date=str(getattr(ds, "StudyDate", "")),
        body_part=str(getattr(ds, "BodyPartExamined", "")),
        file_path=str(file_path),
      )
    except ImportError:
      return DICOMMetadata(file_path=str(file_path))
    except Exception:
      return DICOMMetadata(file_path=str(file_path))

  def scan_directory(self, directory: Path) -> list[DICOMMetadata]:
    results = []
    for path in directory.rglob("*.dcm"):
      results.append(self.extract_metadata(path))
    return results
