"""Vérification et installation des mises à jour (Releases GitHub).

Trois cas selon la façon dont l'application a été installée :
- installée via l'installateur Windows (Inno Setup, dossier utilisateur) :
  mise à jour complète en un clic — téléchargement du nouvel installateur,
  installation silencieuse, relance automatique ;
- installée depuis le Microsoft Store (paquet MSIX) : rien à faire, le
  Store met l'application à jour lui-même ;
- exécutable portable, macOS, Linux, ou lancement depuis les sources :
  simple notification avec un lien de téléchargement.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from aquabioscope import __version__

REPO = "EmericTruchet/aquabioscope"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
INSTALLER_ASSET = "AquaBioScope-Setup.exe"
USER_AGENT = f"AquaBioScope/{__version__}"
DISABLE_ENV = "AQUABIOSCOPE_NO_UPDATE_CHECK"


class InstallKind(Enum):
    INSTALLER = "installer"  # Inno Setup : mise a jour automatique possible
    STORE = "store"          # MSIX / Microsoft Store : geree par le Store
    OTHER = "other"          # portable, macOS, Linux, sources : notification seule


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    page_url: str
    installer_url: str | None


def parse_version(text: str) -> tuple[int, ...]:
    """"v1.2.3" -> (1, 2, 3) ; les suffixes non numériques sont ignorés."""
    parts = []
    for chunk in text.strip().lstrip("vV").split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def is_newer(candidate: str, current: str = __version__) -> bool:
    return parse_version(candidate) > parse_version(current)


def install_kind() -> InstallKind:
    if not getattr(sys, "frozen", False) or sys.platform != "win32":
        return InstallKind.OTHER
    exe_dir = Path(sys.executable).resolve().parent
    if "WindowsApps" in exe_dir.parts:
        return InstallKind.STORE
    if any(exe_dir.glob("unins*.exe")):  # desinstalleur pose par Inno Setup
        return InstallKind.INSTALLER
    return InstallKind.OTHER


def check_for_update(timeout: float = 6.0) -> UpdateInfo | None:
    """Interroge GitHub ; renvoie la nouvelle version si elle est plus
    récente que celle en cours, None sinon (ou en cas d'erreur réseau : une
    vérification de mise à jour ne doit jamais gêner l'utilisation)."""
    if os.environ.get(DISABLE_ENV) or install_kind() is InstallKind.STORE:
        return None
    request = urllib.request.Request(
        LATEST_RELEASE_API, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            release = json.load(response)
    except (OSError, ValueError):
        return None
    tag = str(release.get("tag_name") or "")
    if not tag or release.get("draft") or release.get("prerelease") or not is_newer(tag):
        return None
    installer_url = next(
        (a.get("browser_download_url") for a in release.get("assets", []) if a.get("name") == INSTALLER_ASSET),
        None,
    )
    return UpdateInfo(
        version=tag.lstrip("vV"),
        page_url=str(release.get("html_url") or RELEASES_PAGE),
        installer_url=installer_url,
    )


def download_installer(url: str, progress=None) -> Path:
    """Télécharge l'installateur dans un dossier temporaire. `progress`
    reçoit (octets reçus, taille totale ou 0)."""
    target = Path(tempfile.mkdtemp(prefix="aquabioscope-update-")) / INSTALLER_ASSET
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response, target.open("wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        received = 0
        while chunk := response.read(256 * 1024):
            out.write(chunk)
            received += len(chunk)
            if progress:
                progress(received, total)
    if total and received != total:
        raise OSError("Téléchargement incomplet")
    return target


def launch_silent_install(installer: Path) -> None:
    """Lance l'installateur en mode silencieux et détaché : il attend que
    l'application soit fermée (l'appelant doit quitter juste après),
    remplace les fichiers puis relance l'application (voir installer/AquaBioScope.iss)."""
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
        creationflags=flags, close_fds=True,
    )
