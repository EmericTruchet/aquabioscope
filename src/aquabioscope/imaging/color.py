"""Corrections colorimétriques adaptées à la photo sous-marine.

Presets fixes (voir `PRESETS`), dosés automatiquement selon la dominante
d'eau mesurée sur chaque photo :
- "naturel"    : correction équilibrée, sûre sur la plupart des photos.
- "profondeur" : correction forte + dévoilage, photos en lumière naturelle.
- "macro"      : contraste, couleurs et netteté pour les photos au flash.
- "vert"       : eaux vertes (Atlantique, Manche, lacs).
- "nb"         : noir & blanc contrasté.
Les presets personnalisés "+" (CustomPresetParams) gardent le moteur v1
(restore_red_channel, gray_world_balance, CLAHE...) : les réglages déjà
enregistrés par l'utilisateur rendent exactement comme avant.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np


def restore_red_channel(rgb_float: np.ndarray, strength: float = 1.0, max_gain: float = 4.0) -> np.ndarray:
    """Compense l'absorption du rouge (et l'excès de bleu) en sous-marin.

    Utilise une compensation additive pondérée par le canal vert (méthode
    "gray-world" d'Ancuti et al.), plutôt qu'un simple gain multiplicatif :
    en eau profonde le rouge moyen peut être quasi nul, et un gain
    multiplicatif y devient instable (bruit amplifié, rendu "sale"). La
    compensation additive reste stable même dans ce cas et donne un rendu
    plus naturel.

    `max_gain` est conservé comme paramètre d'API mais n'est plus utilisé
    par cette méthode (gardé pour compatibilité de signature).
    """
    r, g, b = rgb_float[..., 0], rgb_float[..., 1], rgb_float[..., 2]
    mean_r, mean_g, mean_b = float(r.mean()), float(g.mean()), float(b.mean())

    r_new = r + strength * (mean_g - mean_r) * (1 - r) * g
    b_new = b + strength * (mean_g - mean_b) * (1 - b) * g

    corrected = rgb_float.copy()
    corrected[..., 0] = r_new
    corrected[..., 2] = b_new
    return np.clip(corrected, 0.0, 1.0)


def gray_world_balance(rgb_float: np.ndarray, strength: float = 1.0, max_gain: float = 1.6) -> np.ndarray:
    """Rééquilibrage global doux : rapproche les 3 moyennes de canal de leur
    moyenne commune, gain borné pour rester discret (utilisé après
    `restore_red_channel`, pas à sa place)."""
    means = [float(rgb_float[..., c].mean()) for c in range(3)]
    target = sum(means) / 3
    gains = [np.clip(target / max(m, 1e-4), 1 / max_gain, max_gain) for m in means]
    out = rgb_float.copy()
    for c in range(3):
        out[..., c] = rgb_float[..., c] * (1 + strength * (gains[c] - 1))
    return np.clip(out, 0.0, 1.0)


def apply_clahe(rgb_uint8: np.ndarray, clip_limit: float = 2.0, tile: int = 8) -> np.ndarray:
    """Contraste local (CLAHE) appliqué sur la luminance (espace LAB)."""
    lab = cv2.cvtColor(rgb_uint8, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile, tile))
    l2 = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2RGB)


def adjust_saturation(rgb_uint8: np.ndarray, factor: float) -> np.ndarray:
    hsv = cv2.cvtColor(rgb_uint8, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * factor, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)


def unsharp_mask(rgb_uint8: np.ndarray, amount: float = 0.5, radius: float = 3.0) -> np.ndarray:
    blurred = cv2.GaussianBlur(rgb_uint8, (0, 0), radius)
    return cv2.addWeighted(rgb_uint8, 1 + amount, blurred, -amount, 0)


# --- Presets fixes (v2) --------------------------------------------------
#
# Chaque preset mesure d'abord la dominante d'eau de la photo (`water_cast`) :
# une photo au flash (rouge présent) n'a quasiment pas besoin de correction
# de couleur, seulement de contraste ; une photo en lumière naturelle à 15 m
# a besoin de beaucoup de rouge. Les corrections de couleur sont dosées par
# cette mesure, ce qui évite les deux défauts des presets v1 : photos au
# flash "grisées" et eau qui vire au violet.

def _to_float(rgb_uint8: np.ndarray) -> np.ndarray:
    return rgb_uint8.astype(np.float32) / 255


def _to_uint8(f: np.ndarray) -> np.ndarray:
    return (np.clip(f, 0.0, 1.0) * 255 + 0.5).astype(np.uint8)


def _sample(f: np.ndarray, size: int = 400) -> np.ndarray:
    """Sous-échantillon pour les mesures statistiques : rapide, et identique
    que l'image fasse 1600 px (aperçu) ou 4000 px (export)."""
    h, w = f.shape[:2]
    step = max(1, max(h, w) // size)
    return f[::step, ::step]


def _blur_large(x: np.ndarray, sigma: float) -> np.ndarray:
    """Flou gaussien à grand rayon calculé sur une version réduite (bien plus
    rapide en pleine résolution, rendu indiscernable)."""
    h, w = x.shape[:2]
    factor = max(1, int(sigma / 4))
    if factor == 1:
        return cv2.GaussianBlur(x, (0, 0), sigma)
    small = cv2.resize(x, (max(1, w // factor), max(1, h // factor)), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), sigma / factor)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)


def water_cast(f: np.ndarray) -> float:
    """0 = pas de dominante (photo au flash), 1 = forte dominante bleue ou
    verte (rouge absorbé par l'eau)."""
    s = _sample(f)
    mr, mg, mb = (float(s[..., c].mean()) for c in range(3))
    cool = max(mg, mb)
    return float(np.clip((cool - mr) / max(cool, 1e-4) * 1.4, 0.0, 1.0))


def compensate_red(f: np.ndarray, strength: float) -> np.ndarray:
    """Compensation du rouge (et du bleu en eau verte) à partir du vert
    (Ancuti et al.), dosée par le déficit de rouge mesuré."""
    s = _sample(f)
    mr, mg, mb = (float(s[..., c].mean()) for c in range(3))
    if mg <= 1e-4:
        return f
    deficit = (mg - mr) / mg
    out = f.copy()
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    if deficit > 0:
        out[..., 0] = r + strength * deficit * deficit * 1.2 * (1 - r) * g
    if mb < mg:  # eau verte : le bleu manque aussi
        out[..., 2] = b + strength * 0.8 * (mg - mb) / mg * (1 - b) * g
    return np.clip(out, 0.0, 1.0)


def dehaze(f: np.ndarray, amount: float) -> np.ndarray:
    """Retire le voile laiteux de l'eau : estime la lumière diffusée par le
    "canal sombre" (Dark Channel Prior) lissé, la soustrait et ré-étire."""
    if amount <= 0:
        return f
    h, w = f.shape[:2]
    factor = max(1, max(h, w) // 400)
    small = cv2.resize(f, (max(1, w // factor), max(1, h // factor)), interpolation=cv2.INTER_AREA)
    dark = small.min(axis=2)
    k = max(3, int(max(small.shape[:2]) * 0.02) | 1)
    dark = cv2.erode(dark, np.ones((k, k), np.uint8))
    dark = cv2.GaussianBlur(dark, (0, 0), k)
    dark = cv2.resize(dark, (w, h), interpolation=cv2.INTER_LINEAR)
    airlight = np.percentile(small.reshape(-1, 3), 99, axis=0).astype(np.float32)
    t = np.clip(1 - amount * dark / max(float(airlight.max()), 1e-3), 0.35, 1.0)[..., None]
    return np.clip((f - airlight * (1 - t)) / t, 0.0, 1.0)


def stretch_levels(
    f: np.ndarray, strength: float, cast: float, low: float = 0.5, high: float = 99.5, max_gain: float = 2.0,
) -> np.ndarray:
    """Niveaux automatiques : étirement commun aux 3 canaux (contraste, sans
    changer les couleurs), mélangé à un étirement par canal (qui corrige la
    dominante) dans la proportion `cast`."""
    s = _sample(f)
    llo, lhi = np.percentile(s.mean(axis=2), [low, high])
    target = (f - llo) / max(float(lhi - llo), 1e-3)
    if cast > 0:
        per = np.empty_like(f)
        for c in range(3):
            lo, hi = np.percentile(s[..., c], [low, high])
            per[..., c] = (f[..., c] - lo) / max(float(hi - lo), 1.0 / max_gain)
        target = target + cast * (per - target)
    return np.clip(f + strength * (target - f), 0.0, 1.0).astype(np.float32)


def finish_lab(
    f: np.ndarray, *, neutralize: float = 0.0, clarity: float = 0.0, clarity_radius: float = 0.02,
    contrast: float = 0.0, black: float = 0.0, magenta_guard: float = 0.0,
) -> np.ndarray:
    """Corrections faites dans l'espace LAB, en une seule conversion :
    - `neutralize` : recentre la dominante (a*/b* médians des tons moyens),
      sans jamais pousser vers le magenta ;
    - `clarity` : contraste local à grand rayon (plus doux que CLAHE, sans
      effet "HDR granuleux"), atténué dans les ombres et hautes lumières ;
    - `contrast` / `black` : courbe en S et point noir ;
    - `magenta_guard` : l'eau nettement bleue qui tire vers le rouge (a* > 0)
      est ramenée vers le bleu ; les roses/rouges des sujets (b* ~ 0) restent."""
    lab = cv2.cvtColor(f, cv2.COLOR_RGB2LAB)
    lum, a, b = lab[..., 0] / 100, lab[..., 1], lab[..., 2]

    if neutralize > 0:
        s = _sample(lab)
        mask = (s[..., 0] > 15) & (s[..., 0] < 90)
        if mask.sum() >= 50:
            da = float(np.median(s[..., 1][mask]))
            db = float(np.median(s[..., 2][mask]))
            a -= neutralize * (da if da < 0 else da * 0.5)
            b -= neutralize * db

    if clarity > 0:
        detail = lum - _blur_large(lum, max(2.0, clarity_radius * max(f.shape[:2])))
        lum = lum + clarity * detail * (4 * lum * (1 - lum))

    lum = np.clip((lum - black) / (1 - black), 0.0, 1.0)
    if contrast > 0:
        e = 1 + contrast
        lum = np.where(lum < 0.5, 0.5 * (2 * lum) ** e, 1 - 0.5 * (2 * (1 - lum)) ** e)

    if magenta_guard > 0:
        # 1) global : des tons moyens restés roses après correction
        s = _sample(lab)
        mask = (s[..., 0] > 10) & (s[..., 0] < 92)
        if mask.sum() >= 50:
            excess = float(np.median(s[..., 1][mask])) - 1.0
            if excess > 0:
                a -= excess * magenta_guard
        # 2) par pixel : l'eau nettement bleue qui tire vers le rouge
        blueness = np.clip((-b - 8) / 25, 0.0, 1.0) * magenta_guard
        a[:] = np.where(a > 0, a * (1 - blueness) - 3 * blueness, a)

    lab[..., 0] = lum * 100
    return np.clip(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), 0.0, 1.0)


def vibrance(f: np.ndarray, amount: float) -> np.ndarray:
    """Sature davantage les couleurs ternes que les couleurs déjà vives
    (évite le rendu "fluo" d'une saturation uniforme)."""
    hsv = cv2.cvtColor(f, cv2.COLOR_RGB2HSV)
    sat = hsv[..., 1]
    hsv[..., 1] = np.clip(sat + amount * 1.5 * sat * (1 - sat), 0.0, 1.0)
    return np.clip(cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB), 0.0, 1.0)


def sharpen(f: np.ndarray, amount: float, radius: float = 1.2) -> np.ndarray:
    blurred = cv2.GaussianBlur(f, (0, 0), radius)
    return np.clip(f + amount * (f - blurred), 0.0, 1.0)


def preset_naturel(rgb_uint8: np.ndarray) -> np.ndarray:
    """Correction équilibrée, sûre sur la plupart des photos (flash ou non)."""
    f = _to_float(rgb_uint8)
    cast = water_cast(f)
    f = compensate_red(f, 0.8)
    f = stretch_levels(f, 0.7, cast * 0.6)
    f = finish_lab(f, neutralize=0.4 * cast, clarity=0.3, contrast=0.1, magenta_guard=cast)
    return _to_uint8(vibrance(f, 0.25))


def preset_profondeur(rgb_uint8: np.ndarray) -> np.ndarray:
    """Correction marquée + dévoilage — photos en lumière naturelle dominées par le bleu."""
    f = _to_float(rgb_uint8)
    cast = water_cast(f)
    f = compensate_red(f, 1.3)
    f = dehaze(f, 0.6)
    f = stretch_levels(f, 0.9, cast * 0.85)
    f = finish_lab(f, neutralize=0.6 * cast, clarity=0.45, contrast=0.15, magenta_guard=cast)
    return _to_uint8(vibrance(f, 0.35))


def preset_macro(rgb_uint8: np.ndarray) -> np.ndarray:
    """Contraste, couleurs et netteté — sujet déjà éclairé au flash."""
    f = _to_float(rgb_uint8)
    f = stretch_levels(f, 0.6, 0.0, low=0.2, high=99.8)
    f = finish_lab(f, clarity=0.45, clarity_radius=0.01, contrast=0.18, black=0.02)
    return _to_uint8(sharpen(vibrance(f, 0.3), 0.5))


def preset_eau_verte(rgb_uint8: np.ndarray) -> np.ndarray:
    """Eaux vertes (Atlantique, Manche, lacs, ports) : rouge et bleu compensés, dévoilage."""
    f = _to_float(rgb_uint8)
    cast = water_cast(f)
    f = compensate_red(f, 1.2)
    f = dehaze(f, 0.5)
    f = stretch_levels(f, 0.85, cast * 0.8)
    f = finish_lab(f, neutralize=0.8 * cast, clarity=0.4, contrast=0.12, magenta_guard=cast)
    return _to_uint8(vibrance(f, 0.3))


def preset_noir_blanc(rgb_uint8: np.ndarray) -> np.ndarray:
    """Noir & blanc contrasté (mélange de canaux favorisant le rouge, qui
    éclaircit les sujets et assombrit l'eau)."""
    f = dehaze(_to_float(rgb_uint8), 0.4)
    gray = 0.5 * f[..., 0] + 0.35 * f[..., 1] + 0.15 * f[..., 2]
    g = np.repeat(gray[..., None], 3, axis=2).astype(np.float32)
    g = stretch_levels(g, 1.0, 0.0, low=0.3, high=99.7)
    g = finish_lab(g, clarity=0.6, contrast=0.25)
    return _to_uint8(g)


PRESETS: dict[str, Callable[[np.ndarray], np.ndarray]] = {
    "naturel": preset_naturel,
    "profondeur": preset_profondeur,
    "macro": preset_macro,
    "vert": preset_eau_verte,
    "nb": preset_noir_blanc,
}


@dataclass
class CustomPresetParams:
    """Réglages d'un preset "+" personnalisé, ajustés à la main pour une photo."""

    red_strength: float = 0.7   # compensation rouge/bleu (restore_red_channel), 0-2
    gray_balance: float = 0.5   # rééquilibrage gray-world, 0-1
    contrast: float = 1.5       # contraste local CLAHE (clip limit), 0 = désactivé, 0-4
    sharpen: float = 0.0        # netteté (unsharp mask), 0 = désactivé, 0-1
    saturation: float = 1.10    # 0.5-2.0


def apply_custom_preset(rgb_uint8: np.ndarray, params: CustomPresetParams) -> np.ndarray:
    f = rgb_uint8.astype(np.float32) / 255
    f = restore_red_channel(f, strength=params.red_strength)
    f = gray_world_balance(f, strength=params.gray_balance, max_gain=1.6)
    out = (f * 255).astype(np.uint8)
    if params.contrast > 0:
        out = apply_clahe(out, clip_limit=params.contrast)
    if params.sharpen > 0:
        out = unsharp_mask(out, amount=params.sharpen)
    return adjust_saturation(out, params.saturation)
