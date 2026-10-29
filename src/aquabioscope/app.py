"""Point d'entrée de l'application AquaBioScope."""
from __future__ import annotations

import sys
import threading
from importlib import resources
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from aquabioscope import __version__, series
from aquabioscope.imaging.color import CustomPresetParams
from aquabioscope.imaging.crop import CropRect
from aquabioscope.identify import SpeciesIdentifier
from aquabioscope.imaging.loader import load_rgb, make_thumbnail
from aquabioscope.inventory import unique_sorted_species
from aquabioscope.session import DiveSession
from aquabioscope.species import SpeciesCatalog, SpeciesEntry
from aquabioscope.ui.export_screens import ExportProgressWidget, ReadyToExportWidget, SessionCompleteWidget
from aquabioscope.ui.export_worker import ExportWorker
from aquabioscope.ui.onboarding import OnboardingWidget
from aquabioscope.ui.review import ReviewWidget
from aquabioscope.ui.series_dialog import SeriesDialog
from aquabioscope.ui.species_tagging import SpeciesTagWidget
from aquabioscope.ui.theme import STYLESHEET
from aquabioscope.ui.update_banner import UpdateBanner

REVIEW_THUMB_SIZE = 1600
SERIES_THUMB_SIZE = 320
SERIES_MAX_PHOTOS = 24  # rafale plus longue : rare, et le dialogue deviendrait illisible


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"AquaBioScope v{__version__}")
        self.resize(1100, 800)

        self.session: DiveSession | None = None
        self.photos: list[Path] = []
        self.current_index = 0
        self.choices: dict[str, str | CustomPresetParams | None] = {}
        self.choice_keys: dict[str, str] = {}  # vignette choisie, pour rouvrir la photo telle quelle
        self._capture_times: dict[int, float | None] = {}
        self._pending_series: list[int] = []  # photos qui recevront les choix de la photo en cours
        self.species_tags: dict[str, list[SpeciesEntry]] = {}
        self.crops: dict[str, CropRect] = {}
        self.export_worker: ExportWorker | None = None

        self.species_catalog = SpeciesCatalog()
        self.species_identifier = SpeciesIdentifier(self.species_catalog)

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
        self.review.series_choice_made.connect(self._on_series_choice_made)
        self.review.previous_requested.connect(self._go_to_previous_photo)
        self.stack.addWidget(self.review)

        self.species_tag_widget = SpeciesTagWidget(self.species_catalog)
        self.species_tag_widget.tags_confirmed.connect(self._on_tags_confirmed)
        self.species_tag_widget.back_requested.connect(self._on_back_to_review)
        self.stack.addWidget(self.species_tag_widget)

        self.ready_to_export = ReadyToExportWidget()
        self.ready_to_export.export_requested.connect(self._start_export)
        self.ready_to_export.back_requested.connect(self._back_from_ready)
        self.stack.addWidget(self.ready_to_export)

        self.export_progress = ExportProgressWidget()
        self.stack.addWidget(self.export_progress)

        self.session_complete = SessionCompleteWidget(self._on_new_session)
        self.stack.addWidget(self.session_complete)

    def _on_session_ready(self, session: DiveSession) -> None:
        self.session = session
        self.photos = session.scan_photos()
        self._reset_choices()
        self.species_tag_widget.set_identifier(self.species_identifier if session.ai_suggestions else None)
        if session.ai_suggestions:
            # chargement du modele (quelques secondes) pendant le choix du filtre de la 1re photo
            threading.Thread(target=self.species_identifier.preload, daemon=True).start()

        if not self.photos:
            QMessageBox.information(
                self, "Aucune photo",
                f"Aucune photo JPG/RAW trouvée dans {session.input_dir}.",
            )
            return

        self.stack.setCurrentWidget(self.review)
        self._load_current_photo()

    def _reset_choices(self) -> None:
        self.current_index = 0
        self.choices = {}
        self.choice_keys = {}
        self.species_tags = {}
        self.crops = {}
        self._capture_times = {}
        self._pending_series = []

    def _load_current_photo(self) -> None:
        path = self.photos[self.current_index]
        path_str = str(path)
        rgb = load_rgb(path, preview=True)
        thumb = make_thumbnail(rgb, max_size=REVIEW_THUMB_SIZE)
        previous = self._previous_kept_photo()
        self.review.show_photo(
            path, thumb, self.current_index, len(self.photos),
            crop=self.crops.get(path_str),
            previous_crop=self.crops.get(str(previous)) if previous else None,
            selected_key=self.choice_keys.get(path_str),
            deleted=path_str in self.choices and self.choices[path_str] is None,
            done=self.choices.get(path_str) is not None,
            series_count=len(self._series_candidates()),
        )

    # --- series (rafales sur un meme sujet) ---------------------------------

    def _capture_time(self, index: int) -> float | None:
        if index not in self._capture_times:
            self._capture_times[index] = series.capture_times([self.photos[index]])[0]
        return self._capture_times[index]

    def _series_candidates(self) -> list[int]:
        """Photos pas encore traitées, prises juste après la photo en cours."""
        start = self.current_index
        end = min(len(self.photos), start + 1 + SERIES_MAX_PHOTOS)
        times = [None] * start + [self._capture_time(i) for i in range(start, end)]
        result = []
        for index in series.series_candidates(times, start):
            if str(self.photos[index]) in self.choices:
                break  # deja traitee (apres un retour arriere) : la serie s'arrete la
            result.append(index)
        return result

    def _on_series_choice_made(self, path_str: str, preset_key: object, crop: object) -> None:
        candidates = self._series_candidates()
        if not candidates:
            self._on_color_choice_made(path_str, preset_key, crop)
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            current = self.review.render_choice(make_thumbnail(self.review.current_thumb, SERIES_THUMB_SIZE), crop=False)
            previous_signature = series.signature(current)
            tiles = []
            similar_so_far = True
            for index in candidates:
                path = self.photos[index]
                rendered = self.review.render_choice(make_thumbnail(load_rgb(path, preview=True), SERIES_THUMB_SIZE))
                signature = series.signature(rendered)
                # cochee par defaut tant que les photos se ressemblent de proche en proche
                similar_so_far = similar_so_far and (
                    bool(series.similarity(previous_signature, signature) >= series.SIMILARITY_THRESHOLD)
                )
                previous_signature = signature
                tiles.append((index, path, rendered, similar_so_far))
        finally:
            QApplication.restoreOverrideCursor()

        dialog = SeriesDialog((self.photos[self.current_index], current), tiles, parent=self)
        if dialog.exec() != SeriesDialog.DialogCode.Accepted:
            return
        self._pending_series = dialog.selected_indices
        self._on_color_choice_made(path_str, preset_key, crop)

    # --- navigation ---------------------------------------------------------

    def _go_to_previous_photo(self) -> None:
        if self.current_index == 0:
            return
        self._pending_series = []
        self.current_index -= 1
        self._load_current_photo()
        self.stack.setCurrentWidget(self.review)

    def _previous_kept_photo(self) -> Path | None:
        """Dernière photo gardée (non supprimée) avant la photo en cours."""
        for path in reversed(self.photos[: self.current_index]):
            if self.choices.get(str(path)) is not None:
                return path
        return None

    def _set_choice(self, path_str: str, preset_key: object, key_name: str, crop: object) -> None:
        self.choices[path_str] = preset_key  # None => suppression
        self.choice_keys[path_str] = key_name
        if crop is None:
            self.crops.pop(path_str, None)
        else:
            self.crops[path_str] = crop

    def _on_color_choice_made(self, path_str: str, preset_key: object, crop: object) -> None:
        self._set_choice(path_str, preset_key, self.review.selected_key, crop)
        if preset_key is None:
            # especes eventuellement taguees avant un retour au filtre : hors inventaire
            self.species_tags.pop(path_str, None)
            self._pending_series = []
            self._advance_to_next_photo()
            return

        path = self.photos[self.current_index]
        # photo corrigee et recadree, telle que choisie : c'est elle qui est
        # affichee et envoyee a l'IA / Google Lens
        self.species_tag_widget.show_photo(
            path, self.review.current_render, self.current_index, len(self.photos), self.session.region,
            initial=self.species_tags.get(path_str), previous=self._previous_photo_species(),
            series_count=len(self._pending_series),
        )
        self.stack.setCurrentWidget(self.species_tag_widget)

    def _previous_photo_species(self) -> list[SpeciesEntry]:
        previous = self._previous_kept_photo()
        return self.species_tags.get(str(previous), []) if previous else []

    def _on_back_to_review(self, draft_species: list) -> None:
        # L'ecran de revue affiche encore cette photo, avec le filtre choisi :
        # on y revient tel quel, en gardant les especes deja taguees.
        self.species_tags[str(self.photos[self.current_index])] = draft_species
        self._pending_series = []  # la serie se redecide en revalidant le filtre
        self.stack.setCurrentWidget(self.review)

    def _on_tags_confirmed(self, path_str: str, species: list) -> None:
        self.species_tags[path_str] = species
        for index in self._pending_series:
            other = str(self.photos[index])
            self._set_choice(other, self.choices[path_str], self.choice_keys[path_str], self.crops.get(path_str))
            self.species_tags[other] = list(species)
        self._pending_series = []
        self._advance_to_next_photo()

    def _advance_to_next_photo(self) -> None:
        """Passe à la prochaine photo pas encore traitée : après un retour
        arrière, on reprend donc là où on en était."""
        untreated = [i for i, p in enumerate(self.photos) if str(p) not in self.choices]
        following = [i for i in untreated if i > self.current_index]
        if untreated:
            self.current_index = (following or untreated)[0]
            self._load_current_photo()
            self.stack.setCurrentWidget(self.review)
        else:
            self._show_ready_to_export()

    def _show_ready_to_export(self) -> None:
        kept = [str(p) for p in self.photos if self.choices.get(str(p)) is not None]
        species = unique_sorted_species([self.species_tags.get(path_str, []) for path_str in kept])
        self.ready_to_export.set_summary(
            kept=len(kept), deleted=len(self.photos) - len(kept), species=len(species),
            untagged=sum(1 for path_str in kept if not self.species_tags.get(path_str)),
        )
        self.stack.setCurrentWidget(self.ready_to_export)

    def _back_from_ready(self) -> None:
        """Rouvre la dernière photo ; « Photo précédente » permet de remonter."""
        self._pending_series = []
        self.current_index = len(self.photos) - 1
        self._load_current_photo()
        self.stack.setCurrentWidget(self.review)

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
        self._reset_choices()
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
