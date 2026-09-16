"""Génération du fichier d'inventaire biologique (.xlsx) de la session,
au même format que l'inventaire de référence (Embranchement / Nom
français / Nom latin)."""
from __future__ import annotations

from pathlib import Path

import openpyxl
from openpyxl.styles import Font

from aquabioscope.species import EMBRANCHEMENT_ORDER, SpeciesEntry

HEADERS = ["Embranchement", "Nom français", "Nom latin"]


def _sort_key(entry: SpeciesEntry) -> tuple[int, str]:
    try:
        rank = EMBRANCHEMENT_ORDER.index(entry.embranchement)
    except ValueError:
        rank = len(EMBRANCHEMENT_ORDER)
    return (rank, entry.nom_vernaculaire.lower())


def unique_sorted_species(all_tags: list[list[SpeciesEntry]]) -> list[SpeciesEntry]:
    seen: dict[tuple[str, str], SpeciesEntry] = {}
    for tags in all_tags:
        for entry in tags:
            seen[(entry.nom_vernaculaire, entry.nom_scientifique)] = entry
    return sorted(seen.values(), key=_sort_key)


def write_inventory_xlsx(path: Path, species: list[SpeciesEntry], sheet_name: str = "Inventaire") -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name

    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for entry in species:
        ws.append([entry.embranchement, entry.nom_vernaculaire, entry.nom_scientifique])

    for col, width in zip("ABC", (22, 42, 32)):
        ws.column_dimensions[col].width = width

    wb.save(path)
