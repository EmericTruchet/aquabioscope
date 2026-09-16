"""Export en tâche de fond (thread Qt) pour ne pas geler l'interface
pendant le traitement pleine résolution de toutes les photos retenues."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from functools import partial

from aquabioscope.export import export_photo, slugify
from aquabioscope.imaging.color import PRESETS, CustomPresetParams, apply_custom_preset
from aquabioscope.imaging.loader import load_rgb
from aquabioscope.inventory import unique_sorted_species, write_inventory_xlsx
from aquabioscope.session import DiveSession
from aquabioscope.species import SpeciesEntry


class ExportWorker(QThread):
    progress = Signal(int, int, str)  # (fait, total, nom fichier en cours)
    finished_ok = Signal(int, str)  # (nb photos exportees, chemin xlsx)
    failed = Signal(str)

    def __init__(
        self,
        session: DiveSession,
        photos: list[Path],
        choices: dict[str, str | CustomPresetParams | None],
        species_tags: dict[str, list[SpeciesEntry]],
    ) -> None:
        super().__init__()
        self.session = session
        self.photos = photos
        self.choices = choices
        self.species_tags = species_tags

    def run(self) -> None:
        try:
            self._run()
        except Exception as exc:  # sécurité : ne jamais planter silencieusement
            self.failed.emit(str(exc))

    def _run(self) -> None:
        kept = [p for p in self.photos if self.choices.get(str(p)) is not None]
        total = len(kept)

        for seq, path in enumerate(kept, start=1):
            preset_value = self.choices[str(path)]
            if isinstance(preset_value, CustomPresetParams):
                preset_fn = partial(apply_custom_preset, params=preset_value)
            else:
                preset_fn = PRESETS.get(preset_value)  # None si "original"
            tags = self.species_tags.get(str(path), [])
            species_names = [e.nom_vernaculaire for e in tags]

            rgb_full = load_rgb(path)
            export_photo(
                source_path=path,
                output_dir=self.session.output_dir,
                rgb_full=rgb_full,
                preset_fn=preset_fn,
                dive_site=self.session.dive_site,
                dive_date=self.session.dive_date,
                photographer=self.session.photographer,
                species_names=species_names,
                seq=seq,
            )
            self.progress.emit(seq, total, path.name)

        all_species = unique_sorted_species(list(self.species_tags.values()))
        xlsx_name = f"inventaire_{slugify(self.session.dive_site)}_{self.session.dive_date:%Y%m%d}.xlsx"
        xlsx_path = self.session.output_dir / xlsx_name
        write_inventory_xlsx(xlsx_path, all_species)

        self.finished_ok.emit(total, str(xlsx_path))
