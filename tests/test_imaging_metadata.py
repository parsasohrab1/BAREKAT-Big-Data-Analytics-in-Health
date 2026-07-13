"""Tests for DICOM metadata extraction."""

import pytest

pytest.importorskip("pydicom")

from barekat.imaging.metadata import extract_metadata
from barekat.imaging.synthetic import create_sample_dicom


def test_extract_metadata_from_generated_dicom(tmp_path):
    dcm_path = create_sample_dicom(tmp_path, patient_id="PT99999", modality="CR")
    meta = extract_metadata(dcm_path)
    assert meta.patient_id == "PT99999"
    assert meta.modality == "CR"
    assert meta.study_uid
    assert meta.rows == 512
