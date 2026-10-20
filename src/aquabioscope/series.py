"""Séries de photos : rafales sur un même sujet, à traiter d'un coup.

Deux photos consécutives sont dans la même série quand elles ont été prises
à peu d'intervalle (heure de prise de vue EXIF) et qu'elles se ressemblent
(même lumière, même cadrage général). La ressemblance n'est mesurée qu'à la
demande, sur les quelques photos qui suivent celle en cours.
"""
from __future__ import annotations

import struct
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import piexif

# Reglages verifies sur une plongee reelle (TG-6) : au-dela de 30 s, le
# plongeur est presque toujours passe a un autre sujet ; la ressemblance ne
# sert qu'a couper une serie quand le sujet change d'un coup (un zoom sur le
# meme sujet la fait deja baisser nettement).
SERIES_MAX_GAP_S = 30.0
SIMILARITY_THRESHOLD = 0.4
SIGNATURE_SIZE = 64

_EXIF_IFD_TAG = 0x8769
_DATETIME_ORIGINAL_TAG = 0x9003
_SUBSEC_ORIGINAL_TAG = 0x9291
_EXIF_TIME_FORMAT = "%Y:%m:%d %H:%M:%S"


def _parse_exif_time(value: bytes | str | None, subsec: bytes | str | None = None) -> float | None:
    if not value:
        return None
    if isinstance(value, bytes):
        value = value.decode("ascii", "ignore")
    try:
        stamp = datetime.strptime(value.strip("\x00 ")[:19], _EXIF_TIME_FORMAT).timestamp()
    except ValueError:
        return None
    if subsec:
        if isinstance(subsec, bytes):
            subsec = subsec.decode("ascii", "ignore")
        digits = subsec.strip("\x00 ")
        if digits.isdigit():
            stamp += float(f"0.{digits}")
    return stamp


def _tiff_ascii_tags(data: bytes, wanted: set[int]) -> dict[int, bytes]:
    """Lit quelques balises ASCII d'un fichier de structure TIFF (la plupart
    des RAW : ORF, CR2, NEF, ARW, DNG, PEF...), dont l'en-tête n'est pas
    toujours standard (ex. "IIRO" chez Olympus), ce que piexif refuse."""
    if data[:2] == b"II":
        order = "<"
    elif data[:2] == b"MM":
        order = ">"
    else:
        return {}

    def read_ifd(offset: int) -> dict[int, tuple[int, int, int]]:
        if offset <= 0 or offset + 2 > len(data):
            return {}
        (count,) = struct.unpack_from(order + "H", data, offset)
        entries = {}
        for i in range(min(count, 512)):
            pos = offset + 2 + 12 * i
            if pos + 12 > len(data):
                break
            tag, typ, n, value = struct.unpack_from(order + "HHII", data, pos)
            entries[tag] = (typ, n, value if n > 4 or typ != 2 else pos + 8)
        return entries

    def ascii_value(entry: tuple[int, int, int]) -> bytes | None:
        typ, n, offset = entry
        if typ != 2 or offset + n > len(data):
            return None
        return data[offset:offset + n]

    (ifd0_offset,) = struct.unpack_from(order + "I", data, 4)
    ifd0 = read_ifd(ifd0_offset)
    found = {}
    exif_entry = ifd0.get(_EXIF_IFD_TAG)
    if exif_entry is not None:
        exif = read_ifd(exif_entry[2])
        for tag in wanted:
            if tag in exif and (value := ascii_value(exif[tag])) is not None:
                found[tag] = value
    return found


def capture_time(path: Path) -> float | None:
    """Heure de prise de vue (secondes, avec les fractions si l'appareil les
    note), ou None si le fichier n'en dit rien."""
    try:
        if path.suffix.lower() in {".jpg", ".jpeg"}:
            exif = piexif.load(str(path)).get("Exif", {})
            return _parse_exif_time(exif.get(_DATETIME_ORIGINAL_TAG), exif.get(_SUBSEC_ORIGINAL_TAG))
        with path.open("rb") as f:
            head = f.read(256 * 1024)  # les IFD sont en debut de fichier
        tags = _tiff_ascii_tags(head, {_DATETIME_ORIGINAL_TAG, _SUBSEC_ORIGINAL_TAG})
        return _parse_exif_time(tags.get(_DATETIME_ORIGINAL_TAG), tags.get(_SUBSEC_ORIGINAL_TAG))
    except Exception:
        return None


def capture_times(paths: list[Path]) -> list[float | None]:
    """Heures de prise de vue ; à défaut d'EXIF, la date de modification du
    fichier (conservée lors d'une copie depuis la carte mémoire)."""
    times = []
    for path in paths:
        stamp = capture_time(path)
        if stamp is None:
            try:
                stamp = path.stat().st_mtime
            except OSError:
                stamp = None
        times.append(stamp)
    return times


def signature(rgb: np.ndarray) -> np.ndarray:
    """Empreinte d'une photo : petite image Lab floutée, normalisée."""
    small = cv2.resize(rgb, (SIGNATURE_SIZE, SIGNATURE_SIZE), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), 2)
    lab = cv2.cvtColor(small, cv2.COLOR_RGB2LAB).astype(np.float32)
    return lab


def similarity(sig_a: np.ndarray, sig_b: np.ndarray) -> float:
    """Ressemblance entre deux empreintes, de 0 (rien à voir) à 1 (identiques) :
    moyenne de la proximité des couleurs (lumière, eau) et de la corrélation
    de la luminosité (composition)."""
    color_dist = np.abs(sig_a[..., 1:].mean(axis=(0, 1)) - sig_b[..., 1:].mean(axis=(0, 1))).sum()
    color_score = max(0.0, 1.0 - color_dist / 30.0)
    la, lb = sig_a[..., 0].ravel(), sig_b[..., 0].ravel()
    la, lb = la - la.mean(), lb - lb.mean()
    denom = float(np.sqrt((la * la).sum() * (lb * lb).sum()))
    if denom > 1e-6:
        corr = float((la * lb).sum() / denom)
    else:  # au moins une image unie : identiques seulement si les deux le sont
        corr = 1.0 if (la * la).sum() < 1e-6 and (lb * lb).sum() < 1e-6 else 0.0
    return float(0.5 * color_score + 0.5 * max(0.0, corr))


def series_candidates(times: list[float | None], start: int, max_gap: float = SERIES_MAX_GAP_S) -> list[int]:
    """Indices des photos qui suivent `start` à peu d'intervalle les unes des
    autres (chaîne : chaque photo à moins de `max_gap` de la précédente)."""
    result = []
    for i in range(start + 1, len(times)):
        before, current = times[i - 1], times[i]
        if before is None or current is None or not (0 <= current - before <= max_gap):
            break
        result.append(i)
    return result
