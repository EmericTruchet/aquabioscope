"""Suggestions d'espèces par IA (modèle BioCLIP 2.5, exécuté en local).

Le modèle compare l'image à une liste de noms d'espèces : la partie "image"
du réseau (`visual.onnx`) produit une empreinte de la photo, comparée aux
empreintes des noms scientifiques de la base, pré-calculées au build (voir
scripts/ia_model). Les candidats sont
limités aux espèces de la zone de plongée : c'est ce qui rend la suggestion
fiable (une espèce de Méditerranée ne sera pas confondue avec sa cousine
tropicale).

Répartition entre l'application et le module IA téléchargé :
- les empreintes des noms (`data/especes_ia.npz`, ~20 Mo) sont DANS
  l'application : elles suivent la base d'espèces, qui change à chaque
  version, sans rien retélécharger ;
- le modèle lui-même (~450 Mo) est téléchargé à part, dans le dossier de
  données local, la première fois que les suggestions IA sont activées :
  il change rarement, et les mises à jour de l'application restent légères.
Chaque version de l'application attend un modèle précis (MODEL_NAME) : quand
une mise à jour en change, le nouveau module est proposé au lancement de la
session suivante et l'ancien est supprimé une fois le nouveau installé.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.request
import zipfile
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import numpy as np
from PIL import Image

from aquabioscope import __version__
from aquabioscope.imaging.crop import CropRect
from aquabioscope.species import SpeciesCatalog, SpeciesEntry

MODEL_NAME = "bioclip-2.5-int8"
MODEL_ARCHIVE = f"aquabioscope-ia-{MODEL_NAME}.zip"
MODEL_URL = f"https://github.com/EmericTruchet/aquabioscope/releases/download/modele-ia/{MODEL_ARCHIVE}"
MODEL_SIZE_LABEL = "≈ 450 Mo"
MODEL_FILES = ("visual.onnx", "modele.json")
EMBEDDINGS_FILE = "especes_ia.npz"  # dans aquabioscope/data, calcule pour MODEL_NAME
USER_AGENT = f"AquaBioScope/{__version__}"


def default_models_dir() -> Path:
    """Dossier local (non synchronisé entre machines : le modèle est gros)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "AquaBioScope" / "modele-ia"


def model_dir(root: Path | None = None) -> Path:
    return (root or default_models_dir()) / MODEL_NAME


def is_installed(root: Path | None = None) -> bool:
    directory = model_dir(root)
    return all((directory / name).is_file() for name in MODEL_FILES)


def old_models(root: Path | None = None) -> list[Path]:
    """Modules installés pour une version précédente de l'application."""
    base = root or default_models_dir()
    if not base.is_dir():
        return []
    return [p for p in base.iterdir() if p.is_dir() and p.name != MODEL_NAME and not p.name.startswith(".")]


def default_embeddings_path() -> Path:
    return resources.files("aquabioscope.data") / EMBEDDINGS_FILE


def download_model(progress=None, cancelled=None, root: Path | None = None, url: str = MODEL_URL) -> Path:
    """Télécharge et décompresse le module IA. `progress` reçoit (octets
    reçus, taille totale ou 0) ; `cancelled()` renvoyant True interrompt le
    téléchargement (OSError). Décompression dans un dossier temporaire
    puis renommage : un téléchargement interrompu ne laisse jamais un
    modèle à moitié installé."""
    target = model_dir(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent, prefix=".telechargement-") as tmp:
        archive = Path(tmp) / MODEL_ARCHIVE
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            received = 0
            while chunk := response.read(1024 * 1024):
                if cancelled and cancelled():
                    raise OSError("Téléchargement annulé")
                out.write(chunk)
                received += len(chunk)
                if progress:
                    progress(received, total)
        if total and received != total:
            raise OSError("Téléchargement incomplet")
        extracted = Path(tmp) / "modele"
        try:
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(extracted)
        except zipfile.BadZipFile as exc:
            raise OSError("Archive du module IA invalide") from exc
        if not all((extracted / name).is_file() for name in MODEL_FILES):
            raise OSError("Archive du module IA incomplète")
        if target.exists():
            shutil.rmtree(target)
        extracted.rename(target)
    for old in old_models(root):
        shutil.rmtree(old, ignore_errors=True)
    return target


@dataclass(frozen=True)
class Suggestion:
    entry: SpeciesEntry
    score: float  # probabilite parmi les candidats de la zone (0..1)


def preprocess(rgb: np.ndarray, size: int, mean: list[float], std: list[float]) -> np.ndarray:
    """Comme le prétraitement d'OpenCLIP : plus petit côté ramené à `size`
    (bicubique), recadrage central carré, normalisation. Renvoie un tableau
    (1, 3, size, size) float32."""
    img = Image.fromarray(np.ascontiguousarray(rgb))
    w, h = img.size
    scale = size / min(w, h)
    new_w, new_h = (size, int(size * h / w)) if w <= h else (int(size * w / h), size)
    if scale != 1:
        img = img.resize((new_w, new_h), Image.Resampling.BICUBIC)
    left = int(round((new_w - size) / 2.0))
    top = int(round((new_h - size) / 2.0))
    img = img.crop((left, top, left + size, top + size))
    x = np.asarray(img, dtype=np.float32) / 255.0
    x = (x - np.asarray(mean, dtype=np.float32)) / np.asarray(std, dtype=np.float32)
    return x.transpose(2, 0, 1)[None]


def square_zone(rgb: np.ndarray, zone: CropRect) -> np.ndarray:
    """Extrait la zone choisie, élargie en carré (autour de son centre, dans
    les limites de la photo) : le modèle ne regarde qu'un carré central, une
    zone allongée (murène, gorgone) serait sinon tronquée."""
    h, w = rgb.shape[:2]
    cx, cy = (zone.x + zone.w / 2) * w, (zone.y + zone.h / 2) * h
    side = min(max(zone.w * w, zone.h * h), w, h)
    x0 = int(round(min(max(cx - side / 2, 0), w - side)))
    y0 = int(round(min(max(cy - side / 2, 0), h - side)))
    side = int(round(side))
    return np.ascontiguousarray(rgb[y0:y0 + side, x0:x0 + side])


def rank(
    image_embedding: np.ndarray, text_embeddings: np.ndarray, logit_scale: float, k: int,
) -> list[tuple[int, float]]:
    """Indices des `k` meilleurs candidats et leur probabilité (softmax sur
    les candidats, comme CLIP)."""
    image_embedding = image_embedding / np.linalg.norm(image_embedding)
    logits = logit_scale * (text_embeddings @ image_embedding)
    probs = np.exp(logits - logits.max())
    probs /= probs.sum()
    order = np.argsort(-probs)[:k]
    return [(int(i), float(probs[i])) for i in order]


class SpeciesIdentifier:
    """Charge le modèle à la première utilisation (quelques secondes) ;
    `suggest` peut ensuite être appelé depuis n'importe quel thread."""

    def __init__(
        self, catalog: SpeciesCatalog, root: Path | None = None, embeddings_path: Path | None = None,
    ) -> None:
        self.catalog = catalog
        self._dir = model_dir(root)
        self._embeddings_path = embeddings_path or default_embeddings_path()
        self._lock = threading.Lock()
        self._session = None
        self._input_name = ""
        self._config: dict = {}
        self._names: list[str] = []
        self._name_index: dict[str, int] = {}
        self._text: np.ndarray | None = None
        self._region_cache: dict[str | None, tuple[np.ndarray, list[SpeciesEntry]]] = {}

    def preload(self) -> None:
        """Chargement anticipé, en tâche de fond ; une erreur se manifestera
        (et sera affichée) au premier `suggest`."""
        try:
            self.load()
        except Exception:  # noqa: BLE001
            pass

    def load(self) -> None:
        with self._lock:
            if self._session is not None:
                return
            import onnxruntime as ort  # import differe : ~1 s, inutile si l'IA n'est pas activee

            self._config = json.loads((self._dir / "modele.json").read_text(encoding="utf-8"))
            with np.load(self._embeddings_path) as data:
                embeddings_model = str(data["modele"])
                self._names = [str(n) for n in data["noms"]]
                text = data["empreintes"].astype(np.float32)
            if embeddings_model != self._config.get("nom"):
                raise RuntimeError(
                    f"empreintes calculées pour {embeddings_model}, modèle installé : {self._config.get('nom')}"
                )
            self._name_index = {n: i for i, n in enumerate(self._names)}
            self._text = text / np.linalg.norm(text, axis=1, keepdims=True)
            options = ort.SessionOptions()
            options.log_severity_level = 3
            session = ort.InferenceSession(
                str(self._dir / "visual.onnx"), options, providers=["CPUExecutionProvider"],
            )
            self._input_name = session.get_inputs()[0].name
            self._session = session

    def _candidates(self, region: str | None) -> tuple[np.ndarray, list[SpeciesEntry]]:
        """Une entrée par nom scientifique connu du modèle, pour la zone."""
        if region not in self._region_cache:
            rows, entries, seen = [], [], set()
            for entry in self.catalog.for_region(region):
                name = entry.nom_scientifique.strip()
                if name in seen or name not in self._name_index:
                    continue
                seen.add(name)
                rows.append(self._name_index[name])
                entries.append(entry)
            self._region_cache[region] = (self._text[rows], entries)
        return self._region_cache[region]

    def suggest(self, rgb: np.ndarray, region: str | None, k: int = 5) -> list[Suggestion]:
        self.load()
        cfg = self._config
        x = preprocess(rgb, int(cfg["image_size"]), cfg["mean"], cfg["std"])
        embedding = self._session.run(None, {self._input_name: x})[0][0]
        text, entries = self._candidates(region)
        if not entries:
            return []
        return [Suggestion(entries[i], p) for i, p in rank(embedding, text, float(cfg["logit_scale"]), k)]
