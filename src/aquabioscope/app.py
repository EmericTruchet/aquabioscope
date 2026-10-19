"""Point d'entrée de l'application AquaBioScope."""
from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from aquabioscope import __version__
from aquabioscope.imaging.color import CustomPresetParams
from aquabioscope.imaging.crop import CropRect
from aquabioscope.imaging.loader import load_rgb, make_thumbnail
from aquabioscope.session import DiveSession
from aquabioscope.species import SpeciesCatalog, SpeciesEntry
from aquabioscope.ui.export_screens import ExportProgressWidget, SessionCompleteWidget
from aquabioscope.ui.export_worker import ExportWorker
from aquabioscope.ui.onboarding import OnboardingWidget
from aquabioscope.ui.review import ReviewWidget
from aquabioscope.ui.species_tagging import SpeciesTagWidget
from aquabioscope.ui.theme import STYLESHEET
from aquabioscope.ui.update_banner import UpdateBanner

REVIEW_THUMB_SIZE = 1600


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"AquaBioScope v{__version__}")
        self.resize(1100, 800)

        self.session: DiveSession | None = None
        self.photos: list[Path] = []
        self.current_index = 0
        self.choices: dict[str, str | CustomPresetParams | None] = {}
        self.species_tags: dict[str, list[SpeciesEntry]] = {}
        self.crops: dict[str, CropRect] = {}
        self.export_worker: ExportWorker | None = None

        self.species_catalog = SpeciesCatalog()

        self.stack = QStackedWidget()
        self.update_banner = UpdateBanner()
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.update_banner)
        central_layout.addWidget(self.stack, stretch=1)
        self.setCentralWidget(central)

        self.onboarding = OnboardingWidget()
        self.onboarding.session_ready.connect(self._on_session_ready)
        self.stack.addWidget(self.onboarding)

        self.review = ReviewWidget()
        self.review.choice_made.connect(self._on_color_choice_made)
        self.stack.addWidget(self.review)

        self.species_tag_widget = SpeciesTagWidget(self.species_catalog)
        self.species_tag_widget.tags_confirmed.connect(self._on_tags_confirmed)
        self.species_tag_widget.back_requested.connect(self._on_back_to_review)
        self.stack.addWidget(self.species_tag_widget)

        self.export_progress = ExportProgressWidget()
        self.stack.addWidget(self.export_progress)

        self.session_complete = SessionCompleteWidget(self._on_new_session)
        self.stack.addWidget(self.session_complete)

    def _on_session_ready(self, session: DiveSession) -> None:
        self.session = session
        self.photos = session.scan_photos()
        self.current_index = 0
        self.choices = {}
        self.species_tags = {}
        self.crops = {}

        if not self.photos:
            QMessageBox.information(
                self, "Aucune photo",
                f"Aucune photo JPG/RAW trouvée dans {session.input_dir}.",
            )
            return

        self.stack.setCurrentWidget(self.review)
        self._load_current_photo()

    def _load_current_photo(self) -> None:
        path = self.photos[self.current_index]
        rgb = load_rgb(path, preview=True)
        thumb = make_thumbnail(rgb, max_size=REVIEW_THUMB_SIZE)
        previous = self._previous_kept_photo()
        self.review.show_photo(
            path, thumb, self.current_index, len(self.photos),
            crop=self.crops.get(str(path)),
            previous_crop=self.crops.get(str(previous)) if previous else None,
        )

    def _previous_kept_photo(self) -> Path | None:
        """Dernière photo gardée (non supprimée) avant la photo en cours."""
        for path in reversed(self.photos[: self.current_index]):
            if self.choices.get(str(path)) is not None:
                return path
        return None

    def _on_color_choice_made(self, path_str: str, preset_key: object, crop: object) -> None:
        self.choices[path_str] = preset_key  # None => suppression
        if crop is None:
            self.crops.pop(path_str, None)
        else:
            self.crops[path_str] = crop
        if preset_key is None:
            # especes eventuellement taguees avant un retour au filtre : hors inventaire
            self.species_tags.pop(path_str, None)
            self._advance_to_next_photo()
            return

        path = self.photos[self.current_index]
        self.species_tag_widget.show_photo(
            path, self.review.current_thumb, self.current_index, len(self.photos), self.session.region,
            initial=self.species_tags.get(path_str), previous=self._previous_photo_species(),
        )
        self.stack.setCurrentWidget(self.species_tag_widget)

    def _previous_photo_species(self) -> list[SpeciesEntry]:
        previous = self._previous_kept_photo()
        return self.species_tags.get(str(previous), []) if previous else []

    def _on_back_to_review(self, draft_species: list) -> None:
        # L'ecran de revue affiche encore cette photo, avec le filtre choisi :
        # on y revient tel quel, en gardant les especes deja taguees.
        self.species_tags[str(self.photos[self.current_index])] = draft_species
        self.stack.setCurrentWidget(self.review)

    def _on_tags_confirmed(self, path_str: str, species: list) -> None:
        self.species_tags[path_str] = species
        self._advance_to_next_photo()

    def _advance_to_next_photo(self) -> None:
        self.current_index += 1
        if self.current_index < len(self.photos):
            self._load_current_photo()
            self.stack.setCurrentWidget(self.review)
        else:
            self._start_export()

    def _start_export(self) -> None:
        self.stack.setCurrentWidget(self.export_progress)
        self.export_progress.set_progress(0, sum(1 for v in self.choices.values() if v is not None), "")

        self.export_worker = ExportWorker(self.session, self.photos, self.choices, self.species_tags, self.crops)
        self.export_worker.progress.connect(self.export_progress.set_progress)
        self.export_worker.finished_ok.connect(self._on_export_finished)
        self.export_worker.failed.connect(self._on_export_failed)
        self.export_worker.start()

    def _on_export_finished(self, exported_count: int, xlsx_path: str) -> None:
        deleted = sum(1 for v in self.choices.values() if v is None)
        self.session_complete.set_summary(str(self.session.output_dir), exported_count, deleted, xlsx_path)
        self.stack.setCurrentWidget(self.session_complete)

    def _on_export_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Échec de l'export", message)
        self.stack.setCurrentWidget(self.onboarding)

    def _on_new_session(self) -> None:
        self.session = None
        self.photos = []
        self.choices = {}
        self.species_tags = {}
        self.crops = {}
        self.stack.setCurrentWidget(self.onboarding)


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    icon_path = resources.files("aquabioscope.assets") / "app_icon.ico"
    app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.show()
    window.update_banner.start_check()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
