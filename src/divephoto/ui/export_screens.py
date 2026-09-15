"""Écrans de fin de session : progression de l'export, puis résumé final."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget


class ExportProgressWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        title = QLabel("Export en cours…")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("")
        self.status_label.setObjectName("Subtitle")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedWidth(420)

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(8)
        layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

    def set_progress(self, done: int, total: int, current_name: str) -> None:
        self.progress_bar.setMaximum(max(total, 1))
        self.progress_bar.setValue(done)
        self.status_label.setText(f"{done} / {total} — {current_name}")


class SessionCompleteWidget(QWidget):
    def __init__(self, on_new_session) -> None:
        super().__init__()
        self._output_dir: str | None = None

        title = QLabel("✅ Session terminée")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("Subtitle")
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary_label.setWordWrap(True)

        open_folder_btn = QPushButton("Ouvrir le dossier de sortie")
        open_folder_btn.setObjectName("SecondaryButton")
        open_folder_btn.clicked.connect(self._open_output_dir)

        new_session_btn = QPushButton("Nouvelle session  →")
        new_session_btn.clicked.connect(on_new_session)

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(8)
        layout.addWidget(self.summary_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(16)
        layout.addWidget(open_folder_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(new_session_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

    def set_summary(self, output_dir: str, exported: int, deleted: int, xlsx_path: str) -> None:
        self._output_dir = output_dir
        self.summary_label.setText(
            f"{exported} photo(s) exportée(s), {deleted} écartée(s).\n"
            f"Dossier : {output_dir}\n"
            f"Inventaire biologique : {xlsx_path}"
        )

    def _open_output_dir(self) -> None:
        if self._output_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._output_dir))
