"""Tests for DICOM thumbnail generation."""

import pytest

pytest.importorskip("pydicom")
pytest.importorskip("PIL")

from barekat.imaging.synthetic import create_sample_dicom

from barekat.imaging.thumbnail import generate_thumbnail


def test_generate_thumbnail_png(tmp_path):
    dcm_path = create_sample_dicom(tmp_path)
    png = generate_thumbnail(dcm_path, max_size=128)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
