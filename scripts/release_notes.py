"""Extrait de NOUVEAUTES.md la section d'une version, pour la note de la
Release GitHub (appelé par .github/workflows/build.yml).

Usage : python scripts/release_notes.py v0.5.1 [release_notes.md]
(fichier écrit en UTF-8 ; sans fichier, la note est affichée)
Échoue si la section manque : une version ne doit pas partir sans note.
"""
from __future__ import annotations

import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parents[1] / "NOUVEAUTES.md"


def section(version: str, text: str) -> str | None:
    version = version.strip().lstrip("vV")
    lines, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip().lstrip("vV") == version
            continue
        if inside:
            lines.append(line)
    return "\n".join(lines).strip() if inside else None


def main() -> None:
    notes = section(sys.argv[1], CHANGELOG.read_text(encoding="utf-8"))
    if not notes:
        sys.exit(f"Pas de section « ## {sys.argv[1].lstrip('vV')} » dans NOUVEAUTES.md")
    if len(sys.argv) > 2:
        # fichier plutot que redirection : sous PowerShell, ">" ecrirait de l'UTF-16
        Path(sys.argv[2]).write_text(notes + "\n", encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(notes)


if __name__ == "__main__":
    main()
