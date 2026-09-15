"""Écran de tag d'espèces (faune/flore) pour la photo en cours.

Recherche avec autocomplétion (nom commun ou scientifique), pré-filtrée
par la région de la plongée, embranchement affiché pour chaque résultat
(important en biologie de plongée). Les espèces retenues s'affichent en
"chips" retirables. Une espèce absente de la base peut être ajoutée en
texte libre.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from divephoto.species import SpeciesCatalog, SpeciesEntry
from divephoto.ui.flow_layout import FlowLayout

UNLISTED_EMBRANCHEMENT = "À préciser"
GOOGLE_LENS_URL = "https://lens.google.com/upload"


def _rgb_to_pixmap(rgb: np.ndarray) -> QPixmap:
    rgb = np.ascontiguousarray(rgb)
    h, w, _ = rgb.shape
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class _Badge(QWidget):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.setObjectName("Badge")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        label = QLabel(text)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.addWidget(label)


class _ResultRow(QWidget):
    def __init__(self, entry: SpeciesEntry) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)
        layout.addWidget(_Badge(entry.embranchement))
        name = QLabel(entry.nom_vernaculaire)
        sci = QLabel(entry.nom_scientifique)
        sci.setStyleSheet("font-style: italic; color: #5B6B73;")
        layout.addWidget(name)
        layout.addWidget(sci)
        layout.addStretch()


class _Chip(QWidget):
    remove_clicked = Signal(object)

    def __init__(self, entry: SpeciesEntry) -> None:
        super().__init__()
        self.entry = entry
        self.setObjectName("Chip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        text = entry.nom_vernaculaire
        label = QLabel(text)
        remove_btn = QPushButton("×")
        remove_btn.setObjectName("ChipRemove")
        remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.entry))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 6, 4)
        layout.setSpacing(6)
        layout.addWidget(label)
        layout.addWidget(remove_btn)


class SpeciesTagWidget(QWidget):
    tags_confirmed = Signal(str, list)  # (chemin photo, list[SpeciesEntry])

    def __init__(self, catalog: SpeciesCatalog | None = None) -> None:
        super().__init__()
        self.catalog = catalog or SpeciesCatalog()
        self.region: str | None = None
        self._current_path: Path | None = None
        self._current_rgb: np.ndarray | None = None
        self._selected: list[SpeciesEntry] = []

        self.progress_label = QLabel()
        self.progress_label.setObjectName("ProgressBadge")
        self.filename_label = QLabel()
        self.filename_label.setObjectName("FileName")
        header = QHBoxLayout()
        header.addWidget(self.progress_label)
        header.addSpacing(12)
        header.addWidget(self.filename_label)
        header.addStretch()

        self.preview = QLabel()
        self.preview.setObjectName("MainPreview")
        self.preview.setFixedSize(260, 195)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setScaledContents(False)

        self.lens_btn = QPushButton("🔍 Chercher avec Google Lens")
        self.lens_btn.setObjectName("SecondaryButton")
        self.lens_btn.setToolTip(
            "Copie la photo dans le presse-papiers et ouvre Google Lens dans le navigateur "
            "— colle-la (Ctrl+V) sur la page pour lancer la recherche visuelle."
        )
        self.lens_btn.clicked.connect(self._search_with_google_lens)
        self.lens_hint = QLabel("")
        self.lens_hint.setObjectName("HintBar")
        self.lens_hint.setWordWrap(True)
        self.lens_hint.setFixedWidth(260)

        title = QLabel("Quelles espèces sont visibles sur cette photo ?")
        title.setObjectName("Subtitle")

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Rechercher une espèce (nom commun ou scientifique)…")
        self.search_edit.textChanged.connect(self._on_query_changed)
        self.search_edit.returnPressed.connect(self._on_return_pressed)

        self.add_custom_btn = QPushButton("+ Ajouter comme espèce non répertoriée")
        self.add_custom_btn.setObjectName("SecondaryButton")
        self.add_custom_btn.setEnabled(False)
        self.add_custom_btn.clicked.connect(self._add_custom)

        search_row = QHBoxLayout()
        search_row.addWidget(self.search_edit, stretch=1)
        search_row.addWidget(self.add_custom_btn)

        self.results_list = QListWidget()
        self.results_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.results_list.itemActivated.connect(self._on_result_activated)

        chips_title = QLabel("Espèces taguées sur cette photo :")
        chips_title.setObjectName("FieldLabel")
        self.chips_container = QWidget()
        self.chips_layout = FlowLayout(self.chips_container, spacing=8)
        self.chips_container.setMinimumHeight(40)

        hint = QLabel("Entrée ajoute le premier résultat  •  clique une espèce taguée pour la retirer")
        hint.setObjectName("HintBar")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.next_btn = QPushButton("Valider les tags et continuer  →")
        self.next_btn.clicked.connect(self._confirm)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(self.next_btn)

        left_col = QVBoxLayout()
        left_col.addWidget(self.preview)
        left_col.addSpacing(8)
        left_col.addWidget(self.lens_btn)
        left_col.addWidget(self.lens_hint)
        left_col.addStretch()

        right_col = QVBoxLayout()
        right_col.addWidget(title)
        right_col.addLayout(search_row)
        right_col.addWidget(chips_title)
        right_col.addWidget(self.chips_container)
        right_col.addWidget(self.results_list, stretch=1)

        content = QHBoxLayout()
        content.addLayout(left_col)
        content.addSpacing(20)
        content.addLayout(right_col, stretch=1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.addLayout(header)
        layout.addLayout(content, stretch=1)
        layout.addWidget(hint)
        layout.addLayout(actions)

        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Return), self, activated=self._confirm)

        self._refresh_results()

    def show_photo(self, path: Path, rgb_thumb: np.ndarray, index: int, total: int, region: str | None) -> None:
        self._current_path = path
        self._current_rgb = rgb_thumb
        self.region = region
        self._selected = []
        self.progress_label.setText(f"Photo {index + 1} / {total}")
        self.filename_label.setText(path.name)
        self.lens_hint.setText("")

        pixmap = _rgb_to_pixmap(rgb_thumb).scaled(
            self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.preview.setPixmap(pixmap)

        self.search_edit.clear()
        self._rebuild_chips()
        self._refresh_results()
        self.search_edit.setFocus()

    def _search_with_google_lens(self) -> None:
        if self._current_rgb is None:
            return
        QApplication.clipboard().setImage(_rgb_to_pixmap(self._current_rgb).toImage())
        QDesktopServices.openUrl(QUrl(GOOGLE_LENS_URL))
        self.lens_hint.setText("Photo copiée — colle-la (Ctrl+V) sur la page Google Lens qui vient de s'ouvrir.")

    def _on_query_changed(self, text: str) -> None:
        self.add_custom_btn.setEnabled(bool(text.strip()))
        self._refresh_results()

    def _refresh_results(self) -> None:
        self.results_list.clear()
        query = self.search_edit.text()
        for entry in self.catalog.search(query, region=self.region, limit=40):
            if entry in self._selected:
                continue
            item = QListWidgetItem()
            row = _ResultRow(entry)
            item.setSizeHint(row.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.results_list.addItem(item)
            self.results_list.setItemWidget(item, row)

    def _on_result_activated(self, item: QListWidgetItem) -> None:
        entry = item.data(Qt.ItemDataRole.UserRole)
        self._add_species(entry)

    def _on_return_pressed(self) -> None:
        if self.results_list.count() > 0:
            entry = self.results_list.item(0).data(Qt.ItemDataRole.UserRole)
            self._add_species(entry)
        elif self.add_custom_btn.isEnabled():
            self._add_custom()

    def _add_custom(self) -> None:
        text = self.search_edit.text().strip()
        if not text:
            return
        entry = SpeciesEntry(
            embranchement=UNLISTED_EMBRANCHEMENT,
            nom_vernaculaire=text,
            nom_scientifique="",
            regions=(),
        )
        self._add_species(entry)

    def _add_species(self, entry: SpeciesEntry) -> None:
        if entry in self._selected:
            return
        self._selected.append(entry)
        self.search_edit.clear()
        self._rebuild_chips()
        self._refresh_results()
        self.search_edit.setFocus()

    def _remove_species(self, entry: SpeciesEntry) -> None:
        self._selected = [e for e in self._selected if e != entry]
        self._rebuild_chips()
        self._refresh_results()

    def _rebuild_chips(self) -> None:
        while self.chips_layout.count():
            item = self.chips_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for entry in self._selected:
            chip = _Chip(entry)
            chip.remove_clicked.connect(self._remove_species)
            self.chips_layout.addWidget(chip)

    def _confirm(self) -> None:
        if self._current_path is None:
            return
        self.tags_confirmed.emit(str(self._current_path), list(self._selected))
