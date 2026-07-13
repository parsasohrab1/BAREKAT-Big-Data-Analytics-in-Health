"""DICOM thumbnail and viewer rendering."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np


def _apply_window_level(pixel_array: np.ndarray, window: float, level: float) -> np.ndarray:
    low = level - window / 2
    high = level + window / 2
    clipped = np.clip(pixel_array.astype(np.float32), low, high)
    if high - low <= 0:
        return np.zeros_like(clipped, dtype=np.uint8)
    normalized = ((clipped - low) / (high - low) * 255.0).astype(np.uint8)
    return normalized


def render_dicom_image(
    file_path: Path,
    *,
    window: float | None = None,
    level: float | None = None,
) -> tuple[np.ndarray, dict]:
    """Render DICOM pixel data to 8-bit grayscale array."""
    import pydicom
    from pydicom.pixel_data_handlers.util import apply_modality_lut

    ds = pydicom.dcmread(str(file_path))
    pixels = apply_modality_lut(ds.pixel_array, ds)

    if window is None or level is None:
        ww = getattr(ds, "WindowWidth", None)
        wc = getattr(ds, "WindowCenter", None)
        window = float(ww[0] if isinstance(ww, (list, tuple)) else (ww or 400))
        level = float(wc[0] if isinstance(wc, (list, tuple)) else (wc or float(np.median(pixels))))

    image = _apply_window_level(pixels, window, level)
    meta = {
        "window": window,
        "level": level,
        "rows": int(image.shape[0]),
        "columns": int(image.shape[1]),
        "modality": str(getattr(ds, "Modality", "")),
    }
    return image, meta


def generate_thumbnail(
    file_path: Path,
    *,
    max_size: int = 256,
    window: float | None = None,
    level: float | None = None,
) -> bytes:
    """Generate PNG thumbnail bytes from a DICOM file."""
    from PIL import Image

    image, _ = render_dicom_image(file_path, window=window, level=level)
    pil_img = Image.fromarray(image, mode="L")

    pil_img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    pil_img.save(buffer, format="PNG")
    return buffer.getvalue()


def render_png_bytes(
    file_path: Path,
    *,
    window: float | None = None,
    level: float | None = None,
) -> bytes:
    """Render full-resolution PNG for viewer."""
    from PIL import Image

    image, _ = render_dicom_image(file_path, window=window, level=level)
    buffer = io.BytesIO()
    Image.fromarray(image, mode="L").save(buffer, format="PNG")
    return buffer.getvalue()
