"""Point d'entrée de l'application DivePhoto."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QStackedWidget
from PySide6.QtCore import Qt

from divephoto.session import DiveSession
from divephoto.ui.onboarding import OnboardingWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DivePhoto")
        self.resize(1000, 700)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.onboarding = OnboardingWidget()
        self.onboarding.session_ready.connect(self._on_session_ready)
        self.stack.addWidget(self.onboarding)

        # Écran de confirmation temporaire (remplacé par l'écran de revue en Phase 2)
        self.summary_label = QLabel()
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.summary_label)

    def _on_session_ready(self, session: DiveSession) -> None:
        photos = session.scan_photos()
        self.summary_label.setText(
            f"Session prête pour « {session.dive_site} » ({session.dive_date}).\n"
            f"{len(photos)} photo(s) trouvée(s) dans {session.input_dir}.\n"
            f"Crédit : {session.credit_text}\n\n"
            "(écran de revue colorimétrique à venir en Phase 2)"
        )
        self.stack.setCurrentWidget(self.summary_label)


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
