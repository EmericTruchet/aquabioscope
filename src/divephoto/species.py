"""Base d'espèces (faune/flore) pour le tag des photos de plongée.

La base embarquée (`data/species.csv`) est volontairement modeste et
éditable à la main : elle part d'un inventaire réel validé en plongée
(Stage Montjoi) plutôt que d'un import automatique non vérifié, ce qui
compte pour un usage d'identification sérieux. Elle est destinée à être
complétée au fil des sessions.
"""
from __future__ import annotations

import csv
import unicodedata
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

# Ordre d'affichage privilégié en plongée biologique (des plus simples aux
# vertébrés), plutôt que l'ordre alphabétique.
EMBRANCHEMENT_ORDER: list[str] = [
    "Végétaux",
    "Eponge",
    "Cnidaire",
    "Cténophore",
    "Ver",
    "Mollusque",
    "Bryozoaire",
    "Arthropode",
    "Echinoderme",
    "Urochordé",
    "Poissons osseux",
    "Poissons cartilagineux",
    "Tétrapode",
]


def _sort_key(embranchement: str) -> tuple[int, str]:
    try:
        return (EMBRANCHEMENT_ORDER.index(embranchement), "")
    except ValueError:
        return (len(EMBRANCHEMENT_ORDER), embranchement)


def _normalize(text: str) -> str:
    """Minuscule et sans accents, pour une recherche tolérante."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


@dataclass(frozen=True)
class SpeciesEntry:
    embranchement: str
    nom_vernaculaire: str
    nom_scientifique: str
    regions: tuple[str, ...]

    @property
    def display_label(self) -> str:
        return f"{self.nom_vernaculaire} ({self.nom_scientifique})"


def _default_csv_path() -> Path:
    return resources.files("divephoto.data") / "species.csv"


def load_species(csv_path: Path | None = None) -> list[SpeciesEntry]:
    path = csv_path or _default_csv_path()
    entries: list[SpeciesEntry] = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            regions = tuple(r.strip() for r in row["regions"].split(",") if r.strip())
            entries.append(
                SpeciesEntry(
                    embranchement=row["embranchement"].strip(),
                    nom_vernaculaire=row["nom_vernaculaire"].strip(),
                    nom_scientifique=row["nom_scientifique"].strip(),
                    regions=regions,
                )
            )
    entries.sort(key=lambda e: (_sort_key(e.embranchement), _normalize(e.nom_vernaculaire)))
    return entries


class SpeciesCatalog:
    """Recherche d'espèces (nom vernaculaire ou scientifique), filtrable par région."""

    def __init__(self, entries: list[SpeciesEntry] | None = None) -> None:
        self.entries = entries if entries is not None else load_species()

    def for_region(self, region: str | None) -> list[SpeciesEntry]:
        if not region or region == "les-deux":
            return list(self.entries)
        return [e for e in self.entries if region in e.regions]

    def search(self, query: str, region: str | None = None, limit: int = 30) -> list[SpeciesEntry]:
        candidates = self.for_region(region)
        query_n = _normalize(query.strip())
        if not query_n:
            return candidates[:limit]

        starts, contains = [], []
        for entry in candidates:
            hay_vern = _normalize(entry.nom_vernaculaire)
            hay_sci = _normalize(entry.nom_scientifique)
            if hay_vern.startswith(query_n) or hay_sci.startswith(query_n):
                starts.append(entry)
            elif query_n in hay_vern or query_n in hay_sci:
                contains.append(entry)
        return (starts + contains)[:limit]
