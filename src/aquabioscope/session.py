"""Modèle de session de plongée : dossiers, métadonnées, crédit photo."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

RAW_EXTENSIONS = {
    ".cr2", ".cr3", ".nef", ".arw", ".orf", ".rw2", ".raf", ".dng", ".pef", ".srw",
}
JPEG_EXTENSIONS = {".jpg", ".jpeg"}
SUPPORTED_EXTENSIONS = RAW_EXTENSIONS | JPEG_EXTENSIONS

# Valeurs possibles pour DiveSession.region, utilisees pour pre-filtrer la
# base d'especes (voir aquabioscope.species.SpeciesCatalog.for_region). La base
# embarquee ne couvre aujourd'hui bien que les deux premieres ; les autres
# zones affichent la base complete (non filtree) faute de donnees dediees.
REGIONS: list[tuple[str, str]] = [
    ("Méditerranée", "mediterranee"),
    ("Atlantique Nord-Est (Europe)", "atlantique"),
    ("Mer Rouge", "mer-rouge"),
    ("Caraïbes", "caraibes"),
    ("Indo-Pacifique", "indo-pacifique"),
    ("Océan Indien", "ocean-indien"),
    ("Pacifique", "pacifique"),
    ("Autre / non renseignée", "autre"),
]


@dataclass
class DiveSession:
    input_dir: Path
    output_dir: Path
    dive_site: str
    dive_date: date
    photographer: str
    region: str = "mediterranee"

    def __post_init__(self) -> None:
        self.input_dir = Path(self.input_dir)
        self.output_dir = Path(self.output_dir)

    @property
    def credit_text(self) -> str:
        return f"{self.dive_site} {self.dive_date.year} © {self.photographer}"

    def scan_photos(self) -> list[Path]:
        """Liste les photos JPG/RAW du dossier d'entree, triees par nom."""
        if not self.input_dir.is_dir():
            return []
        return sorted(
            p for p in self.input_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )
