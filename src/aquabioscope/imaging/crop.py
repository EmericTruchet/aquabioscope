"""Recadrage : rectangle exprimé en fractions de l'image (0-1), pour pouvoir
le définir sur l'aperçu réduit et l'appliquer tel quel à la pleine
résolution à l'export."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CropRect:
    x: float
    y: float
    w: float
    h: float

    def is_full(self) -> bool:
        return self.x <= 1e-4 and self.y <= 1e-4 and self.w >= 1 - 1e-4 and self.h >= 1 - 1e-4


def apply_crop(rgb: np.ndarray, crop: CropRect | None) -> np.ndarray:
    if crop is None or crop.is_full():
        return rgb
    h, w = rgb.shape[:2]
    x0 = int(round(max(0.0, crop.x) * w))
    y0 = int(round(max(0.0, crop.y) * h))
    x1 = int(round(min(1.0, crop.x + crop.w) * w))
    y1 = int(round(min(1.0, crop.y + crop.h) * h))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return rgb
    return np.ascontiguousarray(rgb[y0:y1, x0:x1])
