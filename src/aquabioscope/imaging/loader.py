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
# Apercu embarque juge "pleine taille" (= vrai JPEG de l'appareil, utilisable
# comme base) s'il fait au moins cette fraction de la largeur du RAW.
_FULL_PREVIEW_MIN_RATIO = 0.5
_ALIGN_SIZE = 1200  # cote des images utilisees pour aligner RAW et apercu


def load_rgb(path: Path, preview: bool = False) -> np.ndarray:
    """Décode une photo JPEG ou RAW en tableau numpy RGB uint8 (H, W, 3).

    `preview=True` privilégie la vitesse (affichage à l'écran) ; l'export
    utilise toujours la pleine résolution.
    """
    if path.suffix.lower() in RAW_EXTENSIONS:
        return _load_raw(path, preview=preview)
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)  # respecte l'orientation EXIF
        return np.array(img.convert("RGB"))


def _load_raw(path: Path, preview: bool) -> np.ndarray:
    """Développe un RAW avec le rendu — et les corrections — de l'appareil.

    Un développement "neutre" (LibRaw) est loin du JPEG de l'appareil : pas
    de courbe de contraste ni de réglages couleur de la marque, mais surtout,
    sur les compacts (Olympus TG notamment), pas de correction de la forte
    distorsion de l'objectif, du vignetage et des franges colorées, et un
    bruit bien plus fort (le petit capteur est fortement débruité par
    l'appareil). Ces corrections ne sont appliquées que dans le JPEG.

    Quand le RAW embarque un aperçu JPEG pleine taille (TG-6 : 3200x2400),
    c'est donc lui la base de l'image : il contient tout le traitement de
    l'appareil. Pour l'export, on y ajoute le fin détail du RAW (aligné
    automatiquement sur l'aperçu, débarrassé de son grain), ce qui donne une
    image à la résolution du RAW, plus nette que le JPEG seul. Si
    l'alignement échoue (eau sans aucun relief...), l'aperçu agrandi est
    utilisé tel quel. Sans aperçu pleine taille, repli sur un développement
    LibRaw recalé sur les tons de la vignette embarquée.
    """
    with rawpy.imread(str(path)) as raw:
        reference = _embedded_preview(raw)
        full_size = reference is not None and (
            max(reference.shape[:2]) >= _FULL_PREVIEW_MIN_RATIO * max(raw.sizes.width, raw.sizes.height)
        )
        if full_size and preview:
            return reference
        rgb16 = raw.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=16, half_size=preview)

    if full_size:
        developed = _match_tones(rgb16, _small(reference, _MATCH_SAMPLE_SIZE))
        return _add_raw_detail(reference, developed)

    if reference is not None:
        rgb = _match_tones(rgb16, _small(reference, _MATCH_SAMPLE_SIZE))
    else:
        rgb = _generic_rendering(rgb16)
    return _reduce_chroma_noise(rgb, sigma=0.8 if preview else 1.4)


def _embedded_preview(raw: rawpy.RawPy) -> np.ndarray | None:
    """Aperçu JPEG embarqué dans le RAW, orienté comme la photo."""
    try:
        thumb = raw.extract_thumb()
    except (rawpy.LibRawError, ValueError):
        return None
    try:
        if thumb.format == rawpy.ThumbFormat.JPEG:
            with Image.open(io.BytesIO(thumb.data)) as img:
                preview = np.array(ImageOps.exif_transpose(img).convert("RGB"))
        else:
            preview = np.asarray(thumb.data)
            if preview.ndim != 3 or preview.shape[2] != 3:
                return None
    except Exception:
        return None
    # Une vignette minuscule ne represente pas fidelement les tons de la photo.
    return preview if min(preview.shape[:2]) >= 120 else None


def _small(rgb: np.ndarray, size: int) -> np.ndarray:
    h, w = rgb.shape[:2]
    scale = size / max(h, w)
    if scale >= 1:
        return rgb
    return cv2.resize(rgb, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)


# --- fusion apercu de l'appareil + detail du RAW ---------------------------

def _normalized_coords(points: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Pixels -> coordonnées centrées, normalisées par la demi-diagonale."""
    h, w = shape
    half_diag = 0.5 * np.hypot(w, h)
    return (points - np.array([w / 2, h / 2])) / half_diag


def _fit_lens_model(reference: np.ndarray, developed: np.ndarray) -> np.ndarray | None:
    """Modèle radial reliant l'aperçu (corrigé par l'appareil) au RAW (non
    corrigé) : p_raw = (a + b r² + c r⁴) p_aperçu + t, en coordonnées
    normalisées. Estimé par appariement de points caractéristiques (ORB) et
    moindres carrés itératifs (rejet des faux appariements). Renvoie
    [a, b, c, tx, ty], ou None si l'alignement n'est pas fiable."""
    ref_small = cv2.cvtColor(_small(reference, _ALIGN_SIZE), cv2.COLOR_RGB2GRAY)
    dev_small = cv2.cvtColor(_small(developed, _ALIGN_SIZE), cv2.COLOR_RGB2GRAY)
    orb = cv2.ORB_create(nfeatures=4000)
    kp_ref, des_ref = orb.detectAndCompute(ref_small, None)
    kp_dev, des_dev = orb.detectAndCompute(dev_small, None)
    if des_ref is None or des_dev is None or len(kp_ref) < 50 or len(kp_dev) < 50:
        return None
    matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(des_ref, des_dev, k=2)
    good = [m[0] for m in matches if len(m) == 2 and m[0].distance < 0.75 * m[1].distance]
    if len(good) < 40:
        return None
    p_ref = _normalized_coords(np.float64([kp_ref[m.queryIdx].pt for m in good]), ref_small.shape)
    p_dev = _normalized_coords(np.float64([kp_dev[m.trainIdx].pt for m in good]), dev_small.shape)

    keep = np.ones(len(good), dtype=bool)
    params = None
    for _ in range(5):
        if keep.sum() < 30:
            return None
        u, d = p_ref[keep], p_dev[keep]
        r2 = (u ** 2).sum(axis=1, keepdims=True)
        n = len(u)
        # inconnues [a, b, c, tx, ty] ; 2 equations (x, y) par point
        A = np.zeros((2 * n, 5))
        A[:n, 0], A[:n, 1], A[:n, 2], A[:n, 3] = u[:, 0], u[:, 0] * r2[:, 0], u[:, 0] * r2[:, 0] ** 2, 1
        A[n:, 0], A[n:, 1], A[n:, 2], A[n:, 4] = u[:, 1], u[:, 1] * r2[:, 0], u[:, 1] * r2[:, 0] ** 2, 1
        params, *_ = np.linalg.lstsq(A, np.concatenate([d[:, 0], d[:, 1]]), rcond=None)
        residual = np.linalg.norm(_apply_lens_model(p_ref, params) - p_dev, axis=1)
        threshold = max(3 * np.median(residual[keep]), 0.002)
        keep = residual < threshold
    residual = np.linalg.norm(_apply_lens_model(p_ref, params) - p_dev, axis=1)[keep]
    # fiable : assez de points, erreur mediane < ~1 px a 1200 px
    if keep.sum() < 30 or np.median(residual) > 0.0015:
        return None
    return params


def _apply_lens_model(points: np.ndarray, params: np.ndarray) -> np.ndarray:
    a, b, c, tx, ty = params
    r2 = (points ** 2).sum(axis=1, keepdims=True)
    return points * (a + b * r2 + c * r2 ** 2) + np.array([tx, ty])


def _add_raw_detail(reference: np.ndarray, developed: np.ndarray) -> np.ndarray:
    """Agrandit l'aperçu de l'appareil à la taille du RAW et y ajoute le fin
    détail du RAW (redressé selon le modèle d'objectif estimé), sans son
    grain : seuls les détails nettement au-dessus du niveau de bruit mesuré
    sont gardés (écrêtage doux), sur la luminance uniquement."""
    h, w = developed.shape[:2]
    base = cv2.resize(reference, (w, h), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
    params = _fit_lens_model(reference, developed)
    if params is None:
        return np.clip(base, 0, 255).astype(np.uint8)

    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    grid = _normalized_coords(np.stack([xs.ravel(), ys.ravel()], axis=1), (h, w))
    src = _apply_lens_model(grid, params) * (0.5 * np.hypot(w, h)) + np.array([w / 2, h / 2])
    map_x = src[:, 0].reshape(h, w).astype(np.float32)
    map_y = src[:, 1].reshape(h, w).astype(np.float32)
    aligned = cv2.remap(developed, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    lum = cv2.cvtColor(aligned, cv2.COLOR_RGB2GRAY).astype(np.float32)
    detail = lum - cv2.GaussianBlur(lum, (0, 0), 1.2)
    noise = 1.4826 * float(np.median(np.abs(detail)))  # ecart-type robuste du bruit
    threshold = 1.5 * noise
    cored = np.sign(detail) * np.maximum(np.abs(detail) - threshold, 0.0)
    return np.clip(base + cored[..., None], 0, 255).astype(np.uint8)


# --- RAW sans apercu pleine taille ---------------------------------------

def _reduce_chroma_noise(rgb: np.ndarray, sigma: float) -> np.ndarray:
    """Lisse uniquement la couleur (canaux a/b de l'espace LAB), pas la
    luminance : supprime les "confettis" colorés typiques des RAW en basse
    lumière sans rendre l'image floue."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    for c in (1, 2):
        lab[..., c] = cv2.GaussianBlur(lab[..., c], (0, 0), sigma)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


def _sample(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    step = max(1, max(h, w) // _MATCH_SAMPLE_SIZE)
    return rgb[::step, ::step]


def _match_tones(rgb16: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Spécification d'histogramme par canal : courbe (LUT 16 bits -> 8 bits)
    calculée sur des versions réduites, appliquée à l'image entière. Ne
    nécessite aucun alignement entre les deux images (seules les
    répartitions de tons comptent)."""
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
