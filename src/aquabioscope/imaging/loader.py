"""Décodage des photos (JPEG et RAW) en tableaux numpy RGB."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rawpy
from PIL import Image, ImageOps

from aquabioscope.session import RAW_EXTENSIONS


def load_rgb(path: Path) -> np.ndarray:
    """Décode une photo JPEG ou RAW en tableau numpy RGB uint8 (H, W, 3)."""
    if path.suffix.lower() in RAW_EXTENSIONS:
        with rawpy.imread(str(path)) as raw:
            rgb = raw.postprocess(
                use_camera_wb=True,
                no_auto_bright=False,
                output_bps=8,
            )
        return rgb
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)  # respecte l'orientation EXIF
        return np.array(img.convert("RGB"))


def make_thumbnail(rgb: np.ndarray, max_size: int = 480) -> np.ndarray:
    """Redimensionne un tableau RGB pour un affichage rapide (aperçu)."""
    h, w = rgb.shape[:2]
    scale = min(max_size / max(h, w), 1.0)
    if scale >= 1.0:
        return rgb
    new_w, new_h = int(w * scale), int(h * scale)
    img = Image.fromarray(rgb).resize((new_w, new_h), Image.Resampling.LANCZOS)
    return np.array(img)
