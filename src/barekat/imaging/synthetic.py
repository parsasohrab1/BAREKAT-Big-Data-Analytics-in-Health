"""Synthetic DICOM generation for development and tests."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path


def _generate_uid() -> str:
    return f"2.25.{uuid.uuid4().int >> 64}"


def create_sample_dicom(
    output_dir: Path,
    *,
    patient_id: str = "PT00001",
    modality: str = "CR",
    body_part: str = "CHEST",
    description: str = "Chest X-Ray PA",
) -> Path:
    import numpy as np
    import pydicom
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    output_dir.mkdir(parents=True, exist_ok=True)
    study_uid = _generate_uid()
    series_uid = _generate_uid()
    sop_uid = generate_uid()

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    ds.PatientID = patient_id
    ds.PatientName = f"Test^{patient_id}"
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.SOPInstanceUID = sop_uid
    ds.Modality = modality
    ds.StudyDate = datetime.now().strftime("%Y%m%d")
    ds.StudyTime = datetime.now().strftime("%H%M%S")
    ds.StudyDescription = description
    ds.BodyPartExamined = body_part
    ds.SeriesDescription = description
    ds.InstanceNumber = 1

    rows, cols = 512, 512
    y, x = np.ogrid[:rows, :cols]
    cx, cy = cols // 2, rows // 2
    radius = min(rows, cols) // 2 - 20
    mask = (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2
    pixels = np.zeros((rows, cols), dtype=np.uint16)
    pixels[mask] = 800 + np.random.randint(0, 400, size=mask.sum(), dtype=np.uint16)
    for i in range(-3, 4):
        offset = i * 35
        rib_mask = mask & (np.abs(y - cy - offset) < 3)
        pixels[rib_mask] = 1200

    ds.Rows = rows
    ds.Columns = cols
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = pixels.tobytes()
    ds.WindowCenter = 600
    ds.WindowWidth = 1200

    filename = output_dir / f"{modality}_{patient_id}_{sop_uid[-8:]}.dcm"
    ds.save_as(filename, write_like_original=False)
    return filename
