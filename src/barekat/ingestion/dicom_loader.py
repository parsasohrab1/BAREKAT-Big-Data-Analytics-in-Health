"""DICOM metadata extractor — backward-compatible wrapper."""

from pathlib import Path

from barekat.imaging.metadata import DICOMMetadata, extract_metadata, scan_directory


class DICOMLoader:
    """Extract metadata from DICOM files."""

    def extract_metadata(self, file_path: Path) -> DICOMMetadata:
        return extract_metadata(file_path)

    def scan_directory(self, directory: Path) -> list[DICOMMetadata]:
        return scan_directory(directory)
