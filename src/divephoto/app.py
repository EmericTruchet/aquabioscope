"""Point d'entrée de l'application DivePhoto."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QStackedWidget

from divephoto.imaging.color import CustomPresetParams
from divephoto.imaging.loader import load_rgb, make_thumbnail
from divephoto.session import DiveSession
from divephoto.species import SpeciesCatalog, SpeciesEntry
from divephoto.ui.export_screens import ExportProgressWidget, SessionCompleteWidget
from divephoto.ui.export_worker import ExportWorker
from divephoto.ui.onboarding import OnboardingWidget
from divephoto.ui.review import ReviewWidget
from divephoto.ui.species_tagging import SpeciesTagWidget
from divephoto.ui.theme import STYLESHEET

REVIEW_THUMB_SIZE = 900


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DivePhoto")
        self.resize(1100, 800)

        self.session: DiveSession | None = None
        self.photos: list[Path] = []
        self.current_index = 0
        self.choices: dict[str, str | CustomPresetParams | None] = {}
        self.species_tags: dict[str, list[SpeciesEntry]] = {}
        self._current_thumb = None
        self.export_worker: ExportWorker | None = None

        self.species_catalog = SpeciesCatalog()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.onboarding = OnboardingWidget()
        self.onboarding.session_ready.connect(self._on_session_ready)
        self.stack.addWidget(self.onboarding)

        self.review = ReviewWidget()
        self.review.choice_made.connect(self._on_color_choice_made)
        self.stack.addWidget(self.review)

        self.species_tag_widget = SpeciesTagWidget(self.species_catalog)
        self.species_tag_widget.tags_confirmed.connect(self._on_tags_confirmed)
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
        rgb = load_rgb(path)
        self._current_thumb = make_thumbnail(rgb, max_size=REVIEW_THUMB_SIZE)
        self.review.show_photo(path, self._current_thumb, self.current_index, len(self.photos))

    def _on_color_choice_made(self, path_str: str, preset_key: object) -> None:
        self.choices[path_str] = preset_key  # None => suppression
        if preset_key is None:
            self._advance_to_next_photo()
            return

        path = self.photos[self.current_index]
        self.species_tag_widget.show_photo(
            path, self._current_thumb, self.current_index, len(self.photos), self.session.region
        )
        self.stack.setCurrentWidget(self.species_tag_widget)

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

        self.export_worker = ExportWorker(self.session, self.photos, self.choices, self.species_tags)
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
        self.stack.setCurrentWidget(self.onboarding)


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
