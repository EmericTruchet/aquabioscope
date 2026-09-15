"""Point d'entrée de l'application DivePhoto."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QStackedWidget
from PySide6.QtCore import Qt

from divephoto.imaging.loader import load_rgb, make_thumbnail
from divephoto.session import DiveSession
from divephoto.ui.onboarding import OnboardingWidget
from divephoto.ui.review import ReviewWidget
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
        self.choices: dict[str, str | None] = {}

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.onboarding = OnboardingWidget()
        self.onboarding.session_ready.connect(self._on_session_ready)
        self.stack.addWidget(self.onboarding)

        self.review = ReviewWidget()
        self.review.choice_made.connect(self._on_choice_made)
        self.stack.addWidget(self.review)

        self.summary_label = QLabel()
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.summary_label)

    def _on_session_ready(self, session: DiveSession) -> None:
        self.session = session
        self.photos = session.scan_photos()
        self.current_index = 0
        self.choices = {}

        if not self.photos:
            self.summary_label.setText(
                f"Aucune photo JPG/RAW trouvée dans {session.input_dir}."
            )
            self.stack.setCurrentWidget(self.summary_label)
            return

        self.stack.setCurrentWidget(self.review)
        self._load_current_photo()

    def _load_current_photo(self) -> None:
        path = self.photos[self.current_index]
        rgb = load_rgb(path)
        thumb = make_thumbnail(rgb, max_size=REVIEW_THUMB_SIZE)
        self.review.show_photo(path, thumb, self.current_index, len(self.photos))

    def _on_choice_made(self, path_str: str, preset_key: object) -> None:
        self.choices[path_str] = preset_key  # None => suppression
        self.current_index += 1
        if self.current_index < len(self.photos):
            self._load_current_photo()
        else:
            self._show_summary()

    def _show_summary(self) -> None:
        kept = {k: v for k, v in self.choices.items() if v is not None}
        deleted = len(self.choices) - len(kept)
        counts: dict[str, int] = {}
        for preset_key in kept.values():
            counts[preset_key] = counts.get(preset_key, 0) + 1
        breakdown = "\n".join(f"  - {name} : {n}" for name, n in counts.items())

        self.summary_label.setText(
            f"Revue terminée : {len(self.choices)} photo(s) traitée(s).\n"
            f"Conservées : {len(kept)}\n{breakdown}\n"
            f"Supprimées : {deleted}\n\n"
            "(export vers le dossier de sortie à venir en Phase 4)"
        )
        self.stack.setCurrentWidget(self.summary_label)


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
