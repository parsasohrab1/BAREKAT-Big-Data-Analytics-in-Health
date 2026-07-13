"""Generate synthetic DICOM files for development and testing."""

from __future__ import annotations

import argparse
from pathlib import Path

from barekat.imaging.synthetic import create_sample_dicom


def main():
    parser = argparse.ArgumentParser(description="Generate sample DICOM studies")
    parser.add_argument("--output", default="./data/dicom")
    parser.add_argument("--count", type=int, default=5)
    args = parser.parse_args()

    output = Path(args.output)
    modalities = [
        ("CR", "CHEST", "Chest X-Ray PA"),
        ("CT", "HEAD", "CT Brain"),
        ("MR", "SPINE", "MRI Lumbar Spine"),
        ("DX", "CHEST", "Digital X-Ray"),
        ("US", "ABDOMEN", "Ultrasound Abdomen"),
    ]

    paths = []
    for i in range(args.count):
        mod, body, desc = modalities[i % len(modalities)]
        path = create_sample_dicom(
            output,
            patient_id=f"PT{i + 1:05d}",
            modality=mod,
            body_part=body,
            description=desc,
        )
        paths.append(path)
        print(f"  Created {path.name}")

    print(f"\n{len(paths)} DICOM files saved to {output}")
    print(
        "Ingest: python -c \"from barekat.imaging.store import ingest_directory; "
        "ingest_directory(__import__('pathlib').Path('./data/dicom'))\""
    )


if __name__ == "__main__":
    main()
