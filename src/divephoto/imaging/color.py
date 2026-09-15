"""Corrections colorimétriques adaptées à la photo sous-marine.

Les fonctions de bas niveau sont combinées en 3 presets (voir `PRESETS`) :
- "naturel"    : correction douce, sûre sur la plupart des photos.
- "profondeur" : correction forte du canal rouge + contraste local, pour
                 les photos larges dominées par le bleu/vert (pas de flash).
- "macro"      : correction colorimétrique légère (le flash a déjà restitué
                 les couleurs), contraste local et netteté renforcés.
"""
from __future__ import annotations

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


def preset_naturel(rgb_uint8: np.ndarray) -> np.ndarray:
    """Correction douce et sûre — cas général."""
    f = rgb_uint8.astype(np.float32) / 255
    f = restore_red_channel(f, strength=0.7)
    f = gray_world_balance(f, strength=0.5, max_gain=1.3)
    out = (f * 255).astype(np.uint8)
    out = apply_clahe(out, clip_limit=1.5)
    return adjust_saturation(out, 1.10)


def preset_profondeur(rgb_uint8: np.ndarray) -> np.ndarray:
    """Correction marquée — photos larges dominées par le bleu, sans flash."""
    f = rgb_uint8.astype(np.float32) / 255
    f = restore_red_channel(f, strength=1.3)
    f = gray_world_balance(f, strength=0.8, max_gain=1.6)
    out = (f * 255).astype(np.uint8)
    out = apply_clahe(out, clip_limit=2.5)
    return adjust_saturation(out, 1.25)


def preset_macro(rgb_uint8: np.ndarray) -> np.ndarray:
    """Correction légère + contraste local et netteté — sujet déjà éclairé au flash."""
    f = rgb_uint8.astype(np.float32) / 255
    f = restore_red_channel(f, strength=0.3)
    f = gray_world_balance(f, strength=0.3, max_gain=1.2)
    out = (f * 255).astype(np.uint8)
    out = apply_clahe(out, clip_limit=1.2)
    out = unsharp_mask(out, amount=0.6, radius=3.0)
    return adjust_saturation(out, 1.20)


PRESETS: dict[str, Callable[[np.ndarray], np.ndarray]] = {
    "naturel": preset_naturel,
    "profondeur": preset_profondeur,
    "macro": preset_macro,
}
