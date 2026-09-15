"""Écran d'accueil : dossiers, lieu/date de plongée, crédit photo."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Signal, QDate
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout,
    QDateEdit, QLabel, QFileDialog, QMessageBox,
)

from divephoto.session import DiveSession


class _DirPicker(QWidget):
    def __init__(self, dialog_title: str) -> None:
        super().__init__()
        self._dialog_title = dialog_title
        self.line_edit = QLineEdit()
        browse_btn = QPushButton("Parcourir…")
        browse_btn.clicked.connect(self._browse)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.line_edit)
        layout.addWidget(browse_btn)

    def _browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, self._dialog_title)
        if directory:
            self.line_edit.setText(directory)

    def path(self) -> str:
        return self.line_edit.text().strip()


class OnboardingWidget(QWidget):
    """Formulaire de démarrage de session, émet `session_ready` une fois validé."""

    session_ready = Signal(object)  # DiveSession

    def __init__(self) -> None:
        super().__init__()

        self.input_picker = _DirPicker("Choisir le dossier des photos brutes")
        self.output_picker = _DirPicker("Choisir le dossier de sortie")
        self.dive_site_edit = QLineEdit()
        self.dive_site_edit.setPlaceholderText("ex. Cap de Creus")
        self.photographer_edit = QLineEdit()
        self.photographer_edit.setPlaceholderText("ex. Emeric Truchet")
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")

        form = QFormLayout()
        form.addRow("Dossier des photos brutes :", self.input_picker)
        form.addRow("Dossier de sortie :", self.output_picker)
        form.addRow("Lieu de plongée :", self.dive_site_edit)
        form.addRow("Date de plongée :", self.date_edit)
        form.addRow("Crédit photo (photographe) :", self.photographer_edit)

        start_btn = QPushButton("Commencer")
        start_btn.clicked.connect(self._on_start)

        title = QLabel("<h2>Nouvelle session DivePhoto</h2>")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addStretch()
        layout.addWidget(start_btn)

    def _on_start(self) -> None:
        errors = []
        input_dir = Path(self.input_picker.path()) if self.input_picker.path() else None
        output_dir = Path(self.output_picker.path()) if self.output_picker.path() else None

        if not input_dir or not input_dir.is_dir():
            errors.append("le dossier des photos brutes doit exister")
        if not output_dir:
            errors.append("le dossier de sortie doit être renseigné")
        if not self.dive_site_edit.text().strip():
            errors.append("le lieu de plongée est requis")
        if not self.photographer_edit.text().strip():
            errors.append("le nom du photographe (crédit) est requis")

        if errors:
            QMessageBox.warning(self, "Session incomplète", "Veuillez corriger :\n- " + "\n- ".join(errors))
            return

        output_dir.mkdir(parents=True, exist_ok=True)

        session = DiveSession(
            input_dir=input_dir,
            output_dir=output_dir,
            dive_site=self.dive_site_edit.text().strip(),
            dive_date=self.date_edit.date().toPython(),
            photographer=self.photographer_edit.text().strip(),
        )
        self.session_ready.emit(session)
