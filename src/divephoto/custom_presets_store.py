"""Bibliothèque de presets colorimétriques personnalisés, nommés par
l'utilisateur et conservés d'une session à l'autre.

Stockage : un fichier JSON dans le dossier de profil utilisateur Windows
(%APPDATA%\\DivePhoto\\custom_presets.json), jamais dans l'exécutable —
un .exe compilé est un fichier figé, rien ne peut s'y réécrire après coup.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from divephoto.imaging.color import CustomPresetParams


def default_store_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home()))
    return base / "DivePhoto" / "custom_presets.json"


def load_named_presets(path: Path | None = None) -> dict[str, CustomPresetParams]:
    path = path or default_store_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    presets: dict[str, CustomPresetParams] = {}
    valid_fields = set(CustomPresetParams.__dataclass_fields__)
    for name, params in raw.items():
        if not isinstance(params, dict):
            continue
        filtered = {k: v for k, v in params.items() if k in valid_fields}
        try:
            presets[name] = CustomPresetParams(**filtered)
        except TypeError:
            continue
    return presets


def save_named_presets(presets: dict[str, CustomPresetParams], path: Path | None = None) -> None:
    path = path or default_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {name: asdict(params) for name, params in presets.items()}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
