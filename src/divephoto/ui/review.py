"""Écran de revue colorimétrique.

UX : un grand aperçu adaptatif affiche le preset actuellement retenu
(par défaut "Naturel", puis le dernier choix fait — les photos d'une
même plongée se ressemblent souvent). Une galerie de vignettes permet
de basculer sur l'original ou un autre preset. Valider (clic sur
l'aperçu, bouton, ou Entrée) passe à la photo suivante ; Supprimer
(bouton ou touche Suppr) écarte la photo.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from divephoto.imaging.color import PRESETS

_TILES: list[tuple[str, str]] = [
    ("original", "Original"),
    ("naturel", "Naturel"),
    ("profondeur", "Corrigé profondeur"),
    ("macro", "Macro contraste"),
]
DEFAULT_PRESET = "naturel"


def _rgb_to_pixmap(rgb: np.ndarray) -> QPixmap:
    rgb = np.ascontiguousarray(rgb)
    h, w, _ = rgb.shape
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class _ScalablePreview(QLabel):
    """Aperçu principal : conserve le pixmap source et se redimensionne avec la fenêtre."""

    clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("MainPreview")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(240, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._source: QPixmap | None = None

    def set_source_pixmap(self, pixmap: QPixmap) -> None:
        self._source = pixmap
        self._rescale()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._source is None or self._source.isNull():
            return
        scaled = self._source.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(scaled)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        super().mousePressEvent(event)
        self.clicked.emit()


class _GalleryThumb(QWidget):
    """Vignette cliquable de la galerie (bas d'écran)."""

    clicked = Signal(str)

    def __init__(self, key: str, label: str) -> None:
        super().__init__()
        self._key = key
        self.setObjectName("GalleryThumb")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("selected", "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(150, 104)

        caption = QLabel(label)
        caption.setObjectName("ThumbCaption")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(self.image_label)
        layout.addWidget(caption)

    def set_pixmap(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        super().mousePressEvent(event)
        self.clicked.emit(self._key)


class ReviewWidget(QWidget):
    """Affiche une photo : grand aperçu du preset retenu + galerie pour en changer."""

    choice_made = Signal(str, object)  # (chemin photo, cle preset choisi ou None si supprime)

    def __init__(self) -> None:
        super().__init__()
        self._current_path: Path | None = None
        self._versions: dict[str, QPixmap] = {}
        self._selected_key = DEFAULT_PRESET

        self.progress_label = QLabel()
        self.progress_label.setObjectName("ProgressBadge")
        self.filename_label = QLabel()
        self.filename_label.setObjectName("FileName")

        header = QHBoxLayout()
        header.addWidget(self.progress_label)
        header.addSpacing(12)
        header.addWidget(self.filename_label)
        header.addStretch()

        self.preview = _ScalablePreview()
        self.preview.clicked.connect(self._confirm)

        self._thumbs: dict[str, _GalleryThumb] = {}
        gallery = QHBoxLayout()
        gallery.addStretch()
        for key, label in _TILES:
            thumb = _GalleryThumb(key, label)
            thumb.clicked.connect(self._select)
            gallery.addWidget(thumb)
            self._thumbs[key] = thumb
        gallery.addStretch()

        hint = QLabel(
            "Clique sur l'aperçu (ou Entrée) pour valider  •  1-4 pour changer de version  •  Suppr pour écarter la photo"
        )
        hint.setObjectName("HintBar")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.delete_btn = QPushButton("🗑  Supprimer la photo")
        self.delete_btn.setObjectName("DeleteButton")
        self.delete_btn.clicked.connect(self._delete)

        self.validate_btn = QPushButton("Valider et continuer  →")
        self.validate_btn.clicked.connect(self._confirm)

        actions = QHBoxLayout()
        actions.addWidget(self.delete_btn)
        actions.addStretch()
        actions.addWidget(self.validate_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.addLayout(header)
        layout.addWidget(self.preview, stretch=1)
        layout.addLayout(gallery)
        layout.addWidget(hint)
        layout.addLayout(actions)

        for i, (key, _label) in enumerate(_TILES):
            QShortcut(QKeySequence(str(i + 1)), self, activated=lambda k=key: self._select(k))
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, activated=self._confirm)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, activated=self._confirm)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, activated=self._delete)

    def show_photo(self, path: Path, rgb_thumb: np.ndarray, index: int, total: int) -> None:
        """Affiche une nouvelle photo (déjà décodée + réduite) avec ses 4 versions."""
        self._current_path = path
        self.progress_label.setText(f"Photo {index + 1} / {total}")
        self.filename_label.setText(path.name)

        self._versions = {"original": _rgb_to_pixmap(rgb_thumb)}
        self._thumbs["original"].set_pixmap(self._versions["original"])
        for key, fn in PRESETS.items():
            pixmap = _rgb_to_pixmap(fn(rgb_thumb))
            self._versions[key] = pixmap
            self._thumbs[key].set_pixmap(pixmap)

        # Choix "maintenu" : on garde le dernier preset choisi comme point de
        # depart pour la photo suivante (souvent la meme lumiere/scene).
        self._select(self._selected_key)

    def _select(self, key: str) -> None:
        if key not in self._versions:
            return
        self._selected_key = key
        self.preview.set_source_pixmap(self._versions[key])
        for k, thumb in self._thumbs.items():
            thumb.set_selected(k == key)

    def _confirm(self) -> None:
        if self._current_path is None:
            return
        self.choice_made.emit(str(self._current_path), self._selected_key)

    def _delete(self) -> None:
        if self._current_path is None:
            return
        self.choice_made.emit(str(self._current_path), None)
