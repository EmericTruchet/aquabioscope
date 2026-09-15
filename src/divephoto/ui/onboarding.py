"""Écran d'accueil : dossiers, lieu/date de plongée, crédit photo."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Signal, QDate, QSettings
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout,
    QDateEdit, QLabel, QFileDialog, QMessageBox,
)

from divephoto.session import DiveSession

_ORG, _APP = "DivePhoto", "DivePhoto"


class _DirPicker(QWidget):
    def __init__(self, dialog_title: str) -> None:
        super().__init__()
        self._dialog_title = dialog_title
        self.line_edit = QLineEdit()
        browse_btn = QPushButton("Parcourir…")
        browse_btn.setObjectName("SecondaryButton")
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

    def set_path(self, value: str) -> None:
        self.line_edit.setText(value)


class OnboardingWidget(QWidget):
    """Formulaire de démarrage de session, émet `session_ready` une fois validé."""

    session_ready = Signal(object)  # DiveSession

    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings(_ORG, _APP)

        self.input_picker = _DirPicker("Choisir le dossier des photos brutes")
        self.output_picker = _DirPicker("Choisir le dossier de sortie")
        self.dive_site_edit = QLineEdit()
        self.dive_site_edit.setPlaceholderText("ex. Cap de Creus")
        self.photographer_edit = QLineEdit()
        self.photographer_edit.setPlaceholderText("ex. Emeric Truchet")
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")

        self._restore_last_values()

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.addRow("Dossier des photos brutes", self.input_picker)
        form.addRow("Dossier de sortie", self.output_picker)
        form.addRow("Lieu de plongée", self.dive_site_edit)
        form.addRow("Date de plongée", self.date_edit)
        form.addRow("Crédit photo (photographe)", self.photographer_edit)

        start_btn = QPushButton("Commencer la session  →")
        start_btn.setMinimumHeight(40)
        start_btn.clicked.connect(self._on_start)

        title = QLabel("🤿 Nouvelle session DivePhoto")
        title.setObjectName("Title")
        subtitle = QLabel("Retouche, tags d'espèces et export en un seul passage, photo par photo.")
        subtitle.setObjectName("Subtitle")

        card = QWidget()
        card.setObjectName("Card")
        card.setMaximumWidth(560)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 28, 32, 28)
        card_layout.setSpacing(18)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(6)
        card_layout.addLayout(form)
        card_layout.addSpacing(6)
        card_layout.addWidget(start_btn)

        outer = QHBoxLayout(self)
        outer.addStretch()
        centered = QVBoxLayout()
        centered.addStretch()
        centered.addWidget(card)
        centered.addStretch()
        outer.addLayout(centered)
        outer.addStretch()

    def _restore_last_values(self) -> None:
        last_output = self._settings.value("last_output_dir", "", str)
        last_photographer = self._settings.value("last_photographer", "", str)
        last_site = self._settings.value("last_dive_site", "", str)
        if last_output:
            self.output_picker.set_path(last_output)
        if last_photographer:
            self.photographer_edit.setText(last_photographer)
        if last_site:
            self.dive_site_edit.setText(last_site)

    def _remember_values(self, session: DiveSession) -> None:
        self._settings.setValue("last_output_dir", str(session.output_dir))
        self._settings.setValue("last_photographer", session.photographer)
        self._settings.setValue("last_dive_site", session.dive_site)

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
        self._remember_values(session)
        self.session_ready.emit(session)
