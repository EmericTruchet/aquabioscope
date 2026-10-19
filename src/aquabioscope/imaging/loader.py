"""Décodage des photos (JPEG et RAW) en tableaux numpy RGB."""
from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np
import rawpy
from PIL import Image, ImageOps

from aquabioscope.session import RAW_EXTENSIONS

_MATCH_BINS = 4096
_MATCH_SAMPLE_SIZE = 800  # cote max des images comparees pour calculer la courbe (suffisant et rapide)


def load_rgb(path: Path, preview: bool = False) -> np.ndarray:
    """Décode une photo JPEG ou RAW en tableau numpy RGB uint8 (H, W, 3).

    `preview=True` décode un RAW en demi-résolution (4x plus rapide), pour
    l'affichage à l'écran ; l'export utilise toujours la pleine résolution.
    """
    if path.suffix.lower() in RAW_EXTENSIONS:
        return _load_raw(path, half_size=preview)
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)  # respecte l'orientation EXIF
        return np.array(img.convert("RGB"))


def _load_raw(path: Path, half_size: bool) -> np.ndarray:
    """Développe un RAW avec le rendu de l'appareil photo.

    Un développement "neutre" (LibRaw seul) donne une image terne, plate et
    bruitée, loin du JPEG que l'appareil aurait produit (courbe de contraste,
    saturation, réglages propres à chaque marque). Quand le RAW embarque son
    aperçu JPEG (quasi toujours), on recale donc, canal par canal, la
    répartition des tons du développement sur celle de cet aperçu : on garde
    la pleine résolution du RAW avec le rendu de l'appareil. Sinon, repli sur
    un développement générique (exposition, courbe en S, saturation douce).
    """
    with rawpy.imread(str(path)) as raw:
        rgb16 = raw.postprocess(
            use_camera_wb=True, no_auto_bright=True, output_bps=16, half_size=half_size,
        )
        reference = _embedded_preview(raw)
    rgb = _match_tones(rgb16, reference) if reference is not None else _generic_rendering(rgb16)
    return _reduce_chroma_noise(rgb, sigma=0.8 if half_size else 1.4)


def _reduce_chroma_noise(rgb: np.ndarray, sigma: float) -> np.ndarray:
    """Lisse uniquement la couleur (canaux a/b de l'espace LAB), pas la
    luminance : supprime les "confettis" colorés typiques des RAW en basse
    lumière sans rendre l'image floue — comme le fait l'appareil pour son JPEG."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    for c in (1, 2):
        lab[..., c] = cv2.GaussianBlur(lab[..., c], (0, 0), sigma)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


def _embedded_preview(raw: rawpy.RawPy) -> np.ndarray | None:
    try:
        thumb = raw.extract_thumb()
    except (rawpy.LibRawError, ValueError):
        return None
    try:
        if thumb.format == rawpy.ThumbFormat.JPEG:
            with Image.open(io.BytesIO(thumb.data)) as img:
                img.thumbnail((_MATCH_SAMPLE_SIZE, _MATCH_SAMPLE_SIZE))
                preview = np.array(img.convert("RGB"))
        else:
            preview = np.asarray(thumb.data)
            if preview.ndim != 3 or preview.shape[2] != 3:
                return None
    except Exception:
        return None
    # Une vignette minuscule ne represente pas fidelement les tons de la photo.
    return preview if min(preview.shape[:2]) >= 120 else None


def _sample(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    step = max(1, max(h, w) // _MATCH_SAMPLE_SIZE)
    return rgb[::step, ::step]


def _match_tones(rgb16: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Spécification d'histogramme par canal : courbe (LUT 16 bits -> 8 bits)
    calculée sur des versions réduites, appliquée à l'image entière. Ne
    nécessite aucun alignement entre les deux images (seules les
    répartitions de tons comptent), donc insensible aux différences de
    cadrage/orientation entre le RAW et son aperçu."""
    src = _sample(rgb16)
    out = np.empty(rgb16.shape, dtype=np.uint8)
    for c in range(3):
        src_c = (src[..., c].astype(np.uint32) * _MATCH_BINS) >> 16
        src_cdf = np.bincount(src_c.ravel(), minlength=_MATCH_BINS).cumsum() / src_c.size
        ref_cdf = np.bincount(reference[..., c].ravel(), minlength=256).cumsum() / reference[..., c].size
        lut = np.interp(src_cdf, ref_cdf, np.arange(256))
        # monotone et lisse (evite le posterisage sur les zones peu peuplees)
        lut = np.maximum.accumulate(cv2.GaussianBlur(lut.reshape(1, -1).astype(np.float32), (0, 0), 8).ravel())
        lut8 = np.clip(np.round(lut), 0, 255).astype(np.uint8)
        out[..., c] = lut8[(rgb16[..., c].astype(np.uint32) * _MATCH_BINS) >> 16]
    return out


def _generic_rendering(rgb16: np.ndarray) -> np.ndarray:
    f = rgb16.astype(np.float32) / 65535
    bright = float(np.percentile(_sample(f).mean(axis=2), 99.5))
    f = np.clip(f * np.clip(0.95 / max(bright, 1e-4), 0.8, 6.0), 0.0, 1.0)
    f = np.where(f < 0.5, 0.5 * (2 * f) ** 1.2, 1 - 0.5 * (2 * (1 - f)) ** 1.2)  # courbe en S douce
    out = (f * 255).astype(np.uint8)
    hsv = cv2.cvtColor(out, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.12, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)


def make_thumbnail(rgb: np.ndarray, max_size: int = 480) -> np.ndarray:
    """Redimensionne un tableau RGB pour un affichage rapide (aperçu)."""
    h, w = rgb.shape[:2]
    scale = min(max_size / max(h, w), 1.0)
    if scale >= 1.0:
        return rgb
    new_w, new_h = int(w * scale), int(h * scale)
    img = Image.fromarray(rgb).resize((new_w, new_h), Image.Resampling.LANCZOS)
    return np.array(img)
