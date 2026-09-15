"""Écran de revue colorimétrique.

UX : un grand aperçu adaptatif affiche le preset actuellement retenu
(par défaut "Naturel", puis le dernier choix fait — les photos d'une
même plongée se ressemblent souvent). Une galerie de vignettes permet
de basculer sur l'original, un preset fixe, ou un preset personnalisé
nommé (créé via la tuile "+", conservé d'une session à l'autre — voir
divephoto.custom_presets_store). Valider (clic sur l'aperçu, bouton, ou
Entrée) passe à la photo suivante ; Supprimer (bouton ou touche Suppr)
écarte la photo.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from divephoto.custom_presets_store import load_named_presets, save_named_presets
from divephoto.imaging.color import PRESETS, apply_custom_preset
from divephoto.ui.custom_preset_dialog import CustomPresetDialog

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


MIN_ZOOM = 1.0
MAX_ZOOM = 8.0
_DRAG_THRESHOLD = 4  # px, en-dessous duquel un clic-relâché est traité comme un clic (pas un glissé)


class _ScalablePreview(QLabel):
    """Aperçu principal : se redimensionne avec la fenêtre, et permet de
    zoomer (molette, centré sur le curseur) et de se déplacer dans l'image
    zoomée (glisser-déposer). Un clic simple (sans glissé, hors zoom)
    valide le choix, comme avant."""

    clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("MainPreview")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(240, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._source: QPixmap | None = None
        self._zoom = MIN_ZOOM
        self._pan = QPointF(0, 0)  # decalage (px, espace image mise a l'echelle) par rapport au centre
        self._drag_start: QPointF | None = None
        self._pan_at_drag_start = QPointF(0, 0)
        self._dragged = False

    def set_source_pixmap(self, pixmap: QPixmap) -> None:
        self._source = pixmap
        self._rescale()

    def reset_zoom(self) -> None:
        self._zoom = MIN_ZOOM
        self._pan = QPointF(0, 0)
        self._rescale()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rescale()

    def _fit_size(self) -> tuple[float, float]:
        src = self._source
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0 or src.width() <= 0 or src.height() <= 0:
            return (1.0, 1.0)
        fit_scale = min(w / src.width(), h / src.height())
        return (src.width() * fit_scale, src.height() * fit_scale)

    def _rescale(self) -> None:
        if self._source is None or self._source.isNull():
            return
        fit_w, fit_h = self._fit_size()
        scaled_w, scaled_h = fit_w * self._zoom, fit_h * self._zoom

        scaled = self._source.scaled(
            round(scaled_w), round(scaled_h),
            Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation,
        )

        widget_w, widget_h = self.width(), self.height()
        max_pan_x = max(0.0, (scaled_w - widget_w) / 2)
        max_pan_y = max(0.0, (scaled_h - widget_h) / 2)
        self._pan.setX(max(-max_pan_x, min(max_pan_x, self._pan.x())))
        self._pan.setY(max(-max_pan_y, min(max_pan_y, self._pan.y())))

        origin_x = round((scaled_w - widget_w) / 2 - self._pan.x())
        origin_y = round((scaled_h - widget_h) / 2 - self._pan.y())
        origin_x = max(0, min(origin_x, max(0, scaled.width() - widget_w)))
        origin_y = max(0, min(origin_y, max(0, scaled.height() - widget_h)))
        crop_w = min(widget_w, scaled.width())
        crop_h = min(widget_h, scaled.height())

        self.setPixmap(scaled.copy(origin_x, origin_y, crop_w, crop_h))

    def wheelEvent(self, event) -> None:  # noqa: N802
        if self._source is None or self._source.isNull():
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 1 / 1.15
        new_zoom = max(MIN_ZOOM, min(MAX_ZOOM, self._zoom * factor))
        if new_zoom == self._zoom:
            return

        fit_w, fit_h = self._fit_size()
        widget_w, widget_h = self.width(), self.height()
        old_scaled_w, old_scaled_h = fit_w * self._zoom, fit_h * self._zoom
        cursor = event.position()

        old_origin_x = (old_scaled_w - widget_w) / 2 - self._pan.x()
        old_origin_y = (old_scaled_h - widget_h) / 2 - self._pan.y()
        # point vise (dans l'image mise a l'echelle courante), en fraction [0,1]
        frac_x = (old_origin_x + cursor.x()) / old_scaled_w if old_scaled_w else 0.5
        frac_y = (old_origin_y + cursor.y()) / old_scaled_h if old_scaled_h else 0.5

        self._zoom = new_zoom
        new_scaled_w, new_scaled_h = fit_w * self._zoom, fit_h * self._zoom
        new_origin_x = frac_x * new_scaled_w - cursor.x()
        new_origin_y = frac_y * new_scaled_h - cursor.y()
        self._pan = QPointF(
            (new_scaled_w - widget_w) / 2 - new_origin_x,
            (new_scaled_h - widget_h) / 2 - new_origin_y,
        )
        self._rescale()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        super().mousePressEvent(event)
        self._drag_start = event.position()
        self._pan_at_drag_start = QPointF(self._pan)
        self._dragged = False

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        super().mouseMoveEvent(event)
        if self._drag_start is None or self._source is None:
            return
        delta = event.position() - self._drag_start
        if delta.manhattanLength() > _DRAG_THRESHOLD:
            self._dragged = True
        if self._dragged:
            self._pan = self._pan_at_drag_start + delta
            self._rescale()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        was_dragged = self._dragged
        self._drag_start = None
        self._dragged = False
        if not was_dragged and self._zoom <= MIN_ZOOM + 1e-6:
            self.clicked.emit()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        super().mouseDoubleClickEvent(event)
        self.reset_zoom()


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

        self.caption = QLabel(label)
        self.caption.setObjectName("ThumbCaption")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(self.image_label)
        layout.addWidget(self.caption)

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


class _AddPresetTile(QWidget):
    """Grande tuile "+" en pointillés pour créer un nouveau preset personnalisé."""

    clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("AddPresetTile")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        plus = QLabel("+")
        plus.setObjectName("AddPresetPlus")
        plus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plus.setFixedSize(150, 104)

        caption = QLabel("Nouveau preset")
        caption.setObjectName("ThumbCaption")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(plus)
        layout.addWidget(caption)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        super().mousePressEvent(event)
        self.clicked.emit()


class ReviewWidget(QWidget):
    """Affiche une photo : grand aperçu du preset retenu + galerie pour en changer."""

    choice_made = Signal(str, object)  # (chemin photo, cle/preset choisi ou None si supprime)

    def __init__(self) -> None:
        super().__init__()
        self._current_path: Path | None = None
        self._current_thumb: np.ndarray | None = None
        self._versions: dict[str, QPixmap] = {}
        self._selected_key = DEFAULT_PRESET
        self._named_presets = load_named_presets()

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
        self.gallery_layout = QHBoxLayout()
        self.gallery_layout.addStretch()
        for key, label in _TILES:
            thumb = _GalleryThumb(key, label)
            thumb.clicked.connect(self._select)
            self.gallery_layout.addWidget(thumb)
            self._thumbs[key] = thumb

        self.add_tile = _AddPresetTile()
        self.add_tile.clicked.connect(self._open_new_preset_dialog)
        self.gallery_layout.addWidget(self.add_tile)
        self.gallery_layout.addStretch()

        for name in self._named_presets:
            self._add_named_tile(name)

        hint = QLabel(
            "Clique sur l'aperçu (ou Entrée) pour valider  •  molette pour zoomer, glisser pour se déplacer, "
            "double-clic pour réinitialiser  •  1-4 pour les presets fixes  •  "
            "clic droit sur un preset personnalisé pour le supprimer  •  Suppr pour écarter la photo"
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
        layout.addLayout(self.gallery_layout)
        layout.addWidget(hint)
        layout.addLayout(actions)

        for i, (key, _label) in enumerate(_TILES):
            QShortcut(QKeySequence(str(i + 1)), self, activated=lambda k=key: self._select(k))
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, activated=self._confirm)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, activated=self._confirm)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, activated=self._delete)

    def show_photo(self, path: Path, rgb_thumb: np.ndarray, index: int, total: int) -> None:
        """Affiche une nouvelle photo (déjà décodée + réduite) avec toutes ses versions."""
        self._current_path = path
        self._current_thumb = rgb_thumb
        self.preview.reset_zoom()
        self.progress_label.setText(f"Photo {index + 1} / {total}")
        self.filename_label.setText(path.name)

        self._versions = {"original": _rgb_to_pixmap(rgb_thumb)}
        self._thumbs["original"].set_pixmap(self._versions["original"])
        for key, fn in PRESETS.items():
            pixmap = _rgb_to_pixmap(fn(rgb_thumb))
            self._versions[key] = pixmap
            self._thumbs[key].set_pixmap(pixmap)
        for name, params in self._named_presets.items():
            pixmap = _rgb_to_pixmap(apply_custom_preset(rgb_thumb, params))
            self._versions[name] = pixmap
            self._thumbs[name].set_pixmap(pixmap)

        # Choix "maintenu" : on garde le dernier preset choisi comme point de
        # depart pour la photo suivante (souvent la meme lumiere/scene), sauf
        # s'il a ete supprime entre-temps.
        initial_key = self._selected_key if self._selected_key in self._versions else DEFAULT_PRESET
        self._select(initial_key)

    def _select(self, key: str) -> None:
        if key not in self._versions:
            return
        self._selected_key = key
        self.preview.set_source_pixmap(self._versions[key])
        for k, thumb in self._thumbs.items():
            thumb.set_selected(k == key)

    def _add_named_tile(self, name: str) -> None:
        thumb = _GalleryThumb(name, name)
        thumb.clicked.connect(self._select)
        thumb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        thumb.customContextMenuRequested.connect(lambda _pos, n=name: self._maybe_delete_named(n))
        insert_index = self.gallery_layout.indexOf(self.add_tile)
        self.gallery_layout.insertWidget(insert_index, thumb)
        self._thumbs[name] = thumb

    def _open_new_preset_dialog(self) -> None:
        if self._current_thumb is None:
            return
        dialog = CustomPresetDialog(
            self._current_thumb, existing_names=tuple(self._named_presets), parent=self
        )
        if dialog.exec() != CustomPresetDialog.DialogCode.Accepted:
            return

        name, params = dialog.name, dialog.params
        self._named_presets[name] = params
        save_named_presets(self._named_presets)

        self._add_named_tile(name)
        pixmap = _rgb_to_pixmap(apply_custom_preset(self._current_thumb, params))
        self._versions[name] = pixmap
        self._thumbs[name].set_pixmap(pixmap)
        self._select(name)

    def _maybe_delete_named(self, name: str) -> None:
        reply = QMessageBox.question(
            self, "Supprimer ce preset",
            f"Supprimer définitivement le preset personnalisé « {name} » ?\n"
            "(les photos déjà validées avec ce preset ne sont pas affectées)",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._named_presets.pop(name, None)
        save_named_presets(self._named_presets)

        thumb = self._thumbs.pop(name, None)
        if thumb is not None:
            self.gallery_layout.removeWidget(thumb)
            thumb.deleteLater()
        self._versions.pop(name, None)

        if self._selected_key == name:
            self._select(DEFAULT_PRESET)

    def _confirm(self) -> None:
        if self._current_path is None:
            return
        value = self._named_presets.get(self._selected_key, self._selected_key)
        self.choice_made.emit(str(self._current_path), value)

    def _delete(self) -> None:
        if self._current_path is None:
            return
        self.choice_made.emit(str(self._current_path), None)
