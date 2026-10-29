"""Écran de tag d'espèces (faune/flore) pour la photo en cours.

Recherche avec autocomplétion (nom commun ou scientifique), pré-filtrée
par la région de la plongée, embranchement affiché pour chaque résultat
(important en biologie de plongée). Les espèces retenues s'affichent en
"chips" retirables. Une espèce absente de la base peut être ajoutée en
texte libre. Un bouton reprend les espèces de la photo précédente (série
sur un même sujet), un autre revient au choix du filtre de la photo.

Si les suggestions IA sont activées pour la session, les espèces les plus
probables (parmi celles de la zone de plongée) sont proposées en un clic,
pour la photo entière ou pour une zone encadrée par l'utilisateur. Google
Lens reste le recours quand l'IA hésite : il reçoit la même image (zone
comprise), et un nom copié depuis sa page est recherché ici au retour dans
l'application.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLayout, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from aquabioscope import feedback
from aquabioscope.identify import SpeciesIdentifier, Suggestion, square_zone
from aquabioscope.species import SpeciesCatalog, SpeciesEntry
from aquabioscope.ui.flow_layout import FlowLayout
from aquabioscope.ui.zone_dialog import ZoneDialog

UNLISTED_EMBRANCHEMENT = "À préciser"
GOOGLE_LENS_URL = "https://lens.google.com/upload"
SUGGESTION_COUNT = 5
# En dessous, la 1re suggestion n'est juste qu'1 fois sur 10 sur nos photos de
# reference (7 a 8 fois sur 10 au-dessus) : on oriente alors vers Google Lens.
LOW_CONFIDENCE = 0.5
LENS_NAME_MAX_LEN = 80  # au-dela, le texte copie n'est pas un nom d'espece


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
        if entry.autres_noms:
            others = ", ".join(entry.autres_noms[:3]) + ("…" if len(entry.autres_noms) > 3 else "")
            aka = QLabel(f"aussi : {others}")
            aka.setStyleSheet("color: #8A989F;")
            layout.addWidget(aka)
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


class _SuggestWorker(QThread):
    done = Signal(int, list)  # (jeton de la demande, list[Suggestion])
    failed = Signal(int, str)

    def __init__(self, identifier: SpeciesIdentifier, rgb: np.ndarray, region: str | None, token: int, parent) -> None:
        super().__init__(parent)
        self._identifier = identifier
        self._rgb = rgb
        self._region = region
        self._token = token

    def run(self) -> None:
        try:
            result = self._identifier.suggest(self._rgb, self._region, k=SUGGESTION_COUNT)
        except Exception as exc:  # noqa: BLE001 - modele absent/corrompu, onnxruntime : jamais bloquant
            self.failed.emit(self._token, str(exc))
            return
        self.done.emit(self._token, result)


def _clear_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()


class SpeciesTagWidget(QWidget):
    tags_confirmed = Signal(str, list)  # (chemin photo, list[SpeciesEntry])
    back_requested = Signal(list)  # especes deja taguees (brouillon conserve au retour)

    def __init__(self, catalog: SpeciesCatalog | None = None) -> None:
        super().__init__()
        self.catalog = catalog or SpeciesCatalog()
        self.region: str | None = None
        self._current_path: Path | None = None
        self._current_rgb: np.ndarray | None = None
        self._selected: list[SpeciesEntry] = []
        self._previous: list[SpeciesEntry] = []
        self._identifier: SpeciesIdentifier | None = None
        self._suggestions: list[Suggestion] = []
        self._ai_token = 0  # seule la reponse a la derniere demande est affichee
        self._ai_zone = False
        self._ai_image: np.ndarray | None = None  # image (ou zone) analysee, envoyee aussi a Google Lens
        self._lens_pending = False  # Google Lens ouvert : guetter un nom copie au retour
        self._ai_workers: set[_SuggestWorker] = set()

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
        QApplication.instance().applicationStateChanged.connect(self._on_app_state_changed)
        self.lens_hint = QLabel("")
        self.lens_hint.setObjectName("HintBar")
        self.lens_hint.setWordWrap(True)
        self.lens_hint.setFixedWidth(260)

        title = QLabel("Quelles espèces sont visibles sur cette photo ?")
        title.setObjectName("Subtitle")
        self.series_note = QLabel()
        self.series_note.setObjectName("ProgressBadge")
        self.series_note.hide()

        ai_title = QLabel("✨ Suggestions IA")
        ai_title.setObjectName("FieldLabel")
        self.ai_status = QLabel()
        self.ai_status.setObjectName("HintBar")
        self.whole_photo_btn = QPushButton("↺  Photo entière")
        self.whole_photo_btn.setObjectName("SecondaryButton")
        self.whole_photo_btn.setToolTip("Revenir aux suggestions pour toute la photo")
        self.whole_photo_btn.clicked.connect(self._suggest_whole_photo)
        self.whole_photo_btn.hide()
        self.zone_btn = QPushButton("🎯  Identifier une zone")
        self.zone_btn.setObjectName("SecondaryButton")
        self.zone_btn.setToolTip(
            "Encadrer un sujet précis de la photo (autre espèce, animal petit dans le cadre) "
            "pour que l'IA ne regarde que lui (Ctrl+I)"
        )
        self.zone_btn.clicked.connect(self._identify_zone)
        ai_header = QHBoxLayout()
        ai_header.addWidget(ai_title)
        ai_header.addSpacing(8)
        ai_header.addWidget(self.ai_status)
        ai_header.addStretch()
        ai_header.addWidget(self.whole_photo_btn)
        ai_header.addWidget(self.zone_btn)
        self.suggestions_container = QWidget()
        self.suggestions_layout = FlowLayout(self.suggestions_container, spacing=8)
        self.ai_box = QWidget()
        ai_layout = QVBoxLayout(self.ai_box)
        ai_layout.setContentsMargins(0, 0, 0, 4)
        ai_layout.setSpacing(6)
        ai_layout.addLayout(ai_header)
        ai_layout.addWidget(self.suggestions_container)
        self.ai_box.hide()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Rechercher une espèce (nom commun ou scientifique)…")
        self.search_edit.textChanged.connect(self._on_query_changed)
        self.search_edit.returnPressed.connect(self._on_return_pressed)

        # La recherche floue (secours quand rien ne matche exactement) reste
        # coûteuse sur ~2000 entrées : on ne relance la recherche que quand
        # la frappe marque une pause, pas à chaque caractère.
        self._search_debounce = QTimer(self)
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(150)
        self._search_debounce.timeout.connect(self._refresh_results)

        self.add_custom_btn = QPushButton("+ Ajouter comme espèce non répertoriée")
        self.add_custom_btn.setObjectName("SecondaryButton")
        self.add_custom_btn.setEnabled(False)
        self.add_custom_btn.clicked.connect(self._add_custom)
        self.add_custom_btn.setToolTip(
            "Ajoute le nom tapé tel quel. Il est aussi proposé, anonymement et sans la photo, "
            "à l'équipe AquaBioScope pour enrichir la base d'espèces."
        )
        self.custom_note = QLabel()
        self.custom_note.setObjectName("HintBar")
        self.custom_note.hide()
        self._reported: set[str] = set()  # une seule remontee par nom et par lancement

        search_row = QHBoxLayout()
        search_row.addWidget(self.search_edit, stretch=1)
        search_row.addWidget(self.add_custom_btn)

        self.results_list = QListWidget()
        self.results_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.results_list.itemActivated.connect(self._on_result_activated)

        chips_title = QLabel("Espèces taguées sur cette photo :")
        chips_title.setObjectName("FieldLabel")
        self.same_as_previous_btn = QPushButton("↺  Mêmes espèces que la photo précédente")
        self.same_as_previous_btn.setObjectName("SecondaryButton")
        self.same_as_previous_btn.setToolTip("Ajoute les espèces taguées sur la photo précédente (Ctrl+R)")
        self.same_as_previous_btn.clicked.connect(self._reuse_previous)
        chips_header = QHBoxLayout()
        chips_header.addWidget(chips_title)
        chips_header.addStretch()
        chips_header.addWidget(self.same_as_previous_btn)
        self.chips_container = QWidget()
        self.chips_layout = FlowLayout(self.chips_container, spacing=8)
        self.chips_container.setMinimumHeight(40)

        hint = QLabel(
            "Entrée ajoute le premier résultat  •  × pour retirer une espèce  •  "
            "Ctrl+R mêmes espèces que la précédente  •  Échap retour au filtre"
        )
        hint.setObjectName("HintBar")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.back_btn = QPushButton("←  Retour au filtre")
        self.back_btn.setObjectName("SecondaryButton")
        self.back_btn.clicked.connect(self._go_back)
        self.next_btn = QPushButton("Valider les tags et continuer  →")
        self.next_btn.clicked.connect(self._confirm)
        actions = QHBoxLayout()
        actions.addWidget(self.back_btn)
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
        right_col.addWidget(self.series_note, alignment=Qt.AlignmentFlag.AlignLeft)
        right_col.addWidget(self.ai_box)
        right_col.addLayout(search_row)
        right_col.addWidget(self.custom_note)
        right_col.addLayout(chips_header)
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
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_R), self, activated=self._reuse_previous)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self._go_back)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_I), self, activated=self._identify_zone)
        for n in range(1, SUGGESTION_COUNT + 1):
            QShortcut(
                QKeySequence(Qt.Modifier.CTRL | Qt.Key(Qt.Key.Key_0 + n)), self,
                activated=lambda n=n: self._add_suggestion(n - 1),
            )

        self._refresh_results()

    def set_identifier(self, identifier: SpeciesIdentifier | None) -> None:
        """Active (ou non, avec None) les suggestions IA pour la session."""
        self._identifier = identifier
        self.ai_box.setVisible(identifier is not None)

    def show_photo(
        self, path: Path, rgb_thumb: np.ndarray, index: int, total: int, region: str | None,
        initial: list[SpeciesEntry] | None = None, previous: list[SpeciesEntry] | None = None,
        series_count: int = 0,
    ) -> None:
        """`initial` : espèces déjà taguées (retour depuis le filtre) ;
        `previous` : celles de la photo précédente, pour le bouton ↺ ;
        `series_count` : autres photos de la série qui recevront ces espèces."""
        self.series_note.setText(
            f"📚 Série : ces espèces seront aussi appliquées aux {series_count} autres photos de la série"
            if series_count > 1 else "📚 Série : ces espèces seront aussi appliquées à l'autre photo de la série"
        )
        self.series_note.setVisible(series_count > 0)
        self._current_path = path
        self._current_rgb = rgb_thumb
        self.region = region
        self._selected = list(initial or [])
        self._previous = list(previous or [])
        self.same_as_previous_btn.setEnabled(bool(self._previous))
        self.progress_label.setText(f"Photo {index + 1} / {total}")
        self.filename_label.setText(path.name)
        self.lens_hint.setText("")
        self._lens_pending = False
        self.custom_note.hide()
        self._ai_image = None

        pixmap = _rgb_to_pixmap(rgb_thumb).scaled(
            self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.preview.setPixmap(pixmap)

        self.search_edit.clear()
        self._rebuild_chips()
        self._refresh_results()
        self.search_edit.setFocus()
        if self._identifier is not None:
            self._suggest_whole_photo()

    # --- suggestions IA -------------------------------------------------

    def _suggest_whole_photo(self) -> None:
        if self._current_rgb is None:
            return
        self.whole_photo_btn.hide()
        self._request_suggestions(self._current_rgb, zone=False)

    def _identify_zone(self) -> None:
        if self._identifier is None or self._current_rgb is None:
            return
        dialog = ZoneDialog(self._current_rgb, parent=self)
        if dialog.exec() != ZoneDialog.DialogCode.Accepted:
            return
        if dialog.zone is None:
            self._suggest_whole_photo()
            return
        self.whole_photo_btn.show()
        self._request_suggestions(square_zone(self._current_rgb, dialog.zone), zone=True)

    def _request_suggestions(self, rgb: np.ndarray, zone: bool) -> None:
        self._ai_token += 1
        self._suggestions = []
        self._ai_zone = zone
        self._ai_image = rgb
        self._rebuild_suggestion_chips()
        self.ai_status.setText("analyse de la zone…" if zone else "analyse de la photo…")
        worker = _SuggestWorker(self._identifier, rgb, self.region, self._ai_token, self)
        worker.done.connect(self._on_suggestions)
        worker.failed.connect(self._on_suggestions_failed)
        worker.finished.connect(lambda: self._ai_workers.discard(worker))
        self._ai_workers.add(worker)
        worker.start()

    def _on_suggestions(self, token: int, suggestions: list) -> None:
        if token != self._ai_token:
            return  # reponse a une photo/zone precedente
        self._suggestions = suggestions
        where = "pour la zone encadrée" if self._ai_zone else "pour la photo"
        if not suggestions:
            self.ai_status.setText("aucune suggestion pour cette zone géographique")
        elif suggestions[0].score < LOW_CONFIDENCE:
            self.ai_status.setText(f"{where}  •  ⚠ l'IA hésite : vérifie, ou essaie Google Lens")
            self.lens_hint.setText("L'IA hésite sur cette photo : Google Lens peut aider.")
        else:
            self.ai_status.setText(f"{where}  •  clic ou Ctrl+1…{len(suggestions)} pour ajouter")
            if not self._lens_pending:
                self.lens_hint.setText("")
        self._rebuild_suggestion_chips()

    def _on_suggestions_failed(self, token: int, message: str) -> None:
        if token == self._ai_token:
            self.ai_status.setText(f"indisponible ({message})")

    def _rebuild_suggestion_chips(self) -> None:
        _clear_layout(self.suggestions_layout)
        for n, suggestion in enumerate(self._suggestions, start=1):
            entry = suggestion.entry
            percent = round(100 * suggestion.score)
            btn = QPushButton(f"{n}.  {entry.nom_vernaculaire}   {percent if percent >= 1 else '<1'} %")
            btn.setObjectName("SuggestionChip")
            btn.setToolTip(f"{entry.nom_scientifique} — {entry.embranchement}")
            btn.setEnabled(entry not in self._selected)
            btn.clicked.connect(lambda _=False, e=entry: self._add_species(e))
            self.suggestions_layout.addWidget(btn)

    def _add_suggestion(self, index: int) -> None:
        if index < len(self._suggestions):
            self._add_species(self._suggestions[index].entry)

    def _reuse_previous(self) -> None:
        added = [e for e in self._previous if e not in self._selected]
        if not added:
            return
        self._selected.extend(added)
        self._rebuild_chips()
        self._rebuild_suggestion_chips()
        self._refresh_results()
        self.search_edit.setFocus()

    def _go_back(self) -> None:
        if self._current_path is not None:
            self.back_requested.emit(list(self._selected))

    def _search_with_google_lens(self) -> None:
        if self._current_rgb is None:
            return
        # meme image que l'IA : la zone encadree s'il y en a une
        image = self._ai_image if self._ai_zone and self._ai_image is not None else self._current_rgb
        QApplication.clipboard().setImage(_rgb_to_pixmap(image).toImage())
        QDesktopServices.openUrl(QUrl(GOOGLE_LENS_URL))
        self._lens_pending = True
        what = "Zone copiée" if image is not self._current_rgb else "Photo copiée"
        self.lens_hint.setText(
            f"{what} — colle-la (Ctrl+V) sur la page Google Lens. Copie ensuite le nom trouvé (Ctrl+C) : "
            "il sera recherché ici à ton retour."
        )

    def _on_app_state_changed(self, state: Qt.ApplicationState) -> None:
        """Retour dans l'application après Google Lens : si un nom a été
        copié, on le recherche directement."""
        if not self._lens_pending or state != Qt.ApplicationState.ApplicationActive or not self.isVisible():
            return
        mime = QApplication.clipboard().mimeData()
        if mime is None or mime.hasImage() or not mime.hasText():
            return  # toujours notre photo : rien de copie depuis Lens pour l'instant
        text = " ".join(mime.text().split())
        if not text or len(text) > LENS_NAME_MAX_LEN:
            return
        self._lens_pending = False
        self.search_edit.setText(text)
        self.search_edit.setFocus()
        self.lens_hint.setText("Nom copié depuis Google Lens : vérifie le résultat dans la liste.")

    def _on_query_changed(self, text: str) -> None:
        self.add_custom_btn.setEnabled(bool(text.strip()))
        self._search_debounce.start()

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
        if self._search_debounce.isActive():
            self._search_debounce.stop()
            self._refresh_results()
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
        if text.casefold() not in self._reported:
            self._reported.add(text.casefold())
            feedback.report_unlisted_species(text, self.region)
        self.custom_note.setText(
            f"« {text} » ajoutée. Le nom est proposé anonymement à l'équipe AquaBioScope "
            "pour enrichir la base d'espèces (sans la photo)."
        )
        self.custom_note.show()

    def _add_species(self, entry: SpeciesEntry) -> None:
        if entry in self._selected:
            return
        self._selected.append(entry)
        self.search_edit.clear()
        self._rebuild_chips()
        self._rebuild_suggestion_chips()
        self._refresh_results()
        self.search_edit.setFocus()

    def _remove_species(self, entry: SpeciesEntry) -> None:
        self._selected = [e for e in self._selected if e != entry]
        self._rebuild_chips()
        self._rebuild_suggestion_chips()
        self._refresh_results()

    def _rebuild_chips(self) -> None:
        _clear_layout(self.chips_layout)
        for entry in self._selected:
            chip = _Chip(entry)
            chip.remove_clicked.connect(self._remove_species)
            self.chips_layout.addWidget(chip)

    def _confirm(self) -> None:
        if self._current_path is None:
            return
        self.tags_confirmed.emit(str(self._current_path), list(self._selected))
