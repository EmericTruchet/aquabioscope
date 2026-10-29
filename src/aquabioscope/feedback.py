"""Remontée des espèces absentes de la base, pour l'enrichir.

Quand un utilisateur ajoute une espèce « non répertoriée », son nom est
envoyé à la page site/demande-espece.php du site d'AquaBioScope, qui
regroupe les demandes (consultables dans la page privée de statistiques).
Seuls le nom tapé, la zone de plongée et la version de l'application sont
envoyés : ni photo, ni identifiant.

Hors connexion (fréquent en voyage de plongée), la demande attend dans une
file locale (%APPDATA%\\AquaBioScope\\demandes_en_attente.json) et repart au
lancement suivant. Un échec n'est jamais signalé à l'utilisateur.
"""
from __future__ import annotations

import json
import os
import threading
import urllib.parse
import urllib.request
from pathlib import Path

from aquabioscope import __version__

ENDPOINT = "https://hoxo.fr/aquabioscope/demande-espece.php"
USER_AGENT = f"AquaBioScope/{__version__}"
DISABLE_ENV = "AQUABIOSCOPE_NO_FEEDBACK"
MAX_PENDING = 200  # file plafonnee : une machine jamais connectee ne la fait pas grossir sans fin

_lock = threading.Lock()


def default_queue_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home()))
    return base / "AquaBioScope" / "demandes_en_attente.json"


def _load(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [d for d in data if isinstance(d, dict) and d.get("nom")] if isinstance(data, list) else []


def _save(path: Path, pending: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pending[-MAX_PENDING:], ensure_ascii=False), encoding="utf-8")


def _post(request: dict, timeout: float = 8.0) -> bool:
    body = urllib.parse.urlencode({**request, "version": __version__}).encode()
    http = urllib.request.Request(ENDPOINT, data=body, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(http, timeout=timeout) as response:
            return response.status == 200
    except OSError:
        return False


def flush(path: Path | None = None, send=_post) -> int:
    """Envoie les demandes en attente ; garde celles qui échouent. Renvoie
    le nombre de demandes envoyées."""
    if os.environ.get(DISABLE_ENV):
        return 0
    path = path or default_queue_path()
    with _lock:
        pending = _load(path)
        if not pending:
            return 0
        remaining = []
        for request in pending:
            # hors ligne : inutile d'insister sur les suivantes, elles repartiront plus tard
            if remaining or not send(request):
                remaining.append(request)
        _save(path, remaining)
        return len(pending) - len(remaining)


def report_unlisted_species(name: str, region: str | None, path: Path | None = None, send=_post) -> None:
    """Met la demande en file puis tente l'envoi en tâche de fond."""
    name = " ".join(name.split())[:80]
    if not name or os.environ.get(DISABLE_ENV):
        return
    path = path or default_queue_path()
    with _lock:
        pending = _load(path)
        pending.append({"nom": name, "zone": region or "autre"})
        _save(path, pending)
    threading.Thread(target=flush, args=(path, send), daemon=True).start()


def flush_in_background() -> None:
    threading.Thread(target=flush, daemon=True).start()
