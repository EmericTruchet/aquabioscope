"""Écrans de fin de session : récapitulatif avant export, progression de
l'export, puis résumé final."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget


def _plural(count: int, word: str) -> str:
    """_plural(2, "photo retenue") -> "2 photos retenues"."""
    if count > 1:
        word = " ".join(w + "s" for w in word.split())
    return f"{count} {word}"


class ReadyToExportWidget(QWidget):
    """Toutes les photos sont passées : dernière chance de revenir en arrière
    avant de lancer l'export."""

    export_requested = Signal()
    back_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        title = QLabel("Tout est prêt")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("Subtitle")
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary_label.setWordWrap(True)

        self.warning_label = QLabel("")
        self.warning_label.setObjectName("ProgressBadge")
        self.warning_label.hide()

        back_btn = QPushButton("←  Revenir aux photos")
        back_btn.setObjectName("SecondaryButton")
        back_btn.clicked.connect(self.back_requested)
        self.export_btn = QPushButton("Exporter  →")
        self.export_btn.setDefault(True)
        self.export_btn.clicked.connect(self.export_requested)
        QShortcut(QKeySequence(Qt.Key.Key_Backspace), self, activated=self.back_requested.emit)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(back_btn)
        buttons.addWidget(self.export_btn)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(8)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.warning_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(16)
        layout.addLayout(buttons)
        layout.addStretch()

    def set_summary(self, kept: int, deleted: int, species: int, untagged: int) -> None:
        self.summary_label.setText(
            "Toutes les photos sont passées en revue.\n"
            f"{_plural(kept, 'photo retenue')} · {_plural(deleted, 'écartée')} · "
            f"{_plural(species, 'espèce différente')}"
        )
        self.warning_label.setText(
            f"{_plural(untagged, 'photo retenue')} sans espèce : "
            + ("elles seront exportées mais n'ajoutent" if untagged > 1 else "elle sera exportée mais n'ajoute")
            + " rien à l'inventaire"
        )
        self.warning_label.setVisible(untagged > 0)
        self.export_btn.setEnabled(kept > 0)
        self.export_btn.setFocus()


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
