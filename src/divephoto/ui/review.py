"""Écran de revue colorimétrique : Original + 3 presets, choix ou suppression."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from divephoto.imaging.color import PRESETS

# Ordre d'affichage : (clé interne, libellé, fonction ou None pour l'original)
_TILES: list[tuple[str, str]] = [
    ("original", "Original"),
    ("naturel", "Naturel"),
    ("profondeur", "Corrigé profondeur"),
    ("macro", "Macro contraste"),
]


def _rgb_to_pixmap(rgb: np.ndarray) -> QPixmap:
    rgb = np.ascontiguousarray(rgb)
    h, w, _ = rgb.shape
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class _Tile(QWidget):
    clicked = Signal(str)

    def __init__(self, key: str, label: str) -> None:
        super().__init__()
        self._key = key

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(300, 220)
        self.image_label.setStyleSheet(
            "QLabel { border: 2px solid palette(mid); background: palette(base); }"
        )

        caption = QLabel(label)
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(self.image_label)
        layout.addWidget(caption)

    def set_pixmap(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            self.image_label.width() or 400,
            self.image_label.height() or 300,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (signature Qt)
        super().mousePressEvent(event)
        self.clicked.emit(self._key)


class ReviewWidget(QWidget):
    """Affiche une photo en 4 versions (original + 3 presets) pour choix ou suppression."""

    choice_made = Signal(str, object)  # (chemin photo, cle preset choisi ou None si supprime)

    def __init__(self) -> None:
        super().__init__()
        self._current_path: Path | None = None

        self.progress_label = QLabel()
        self.filename_label = QLabel()
        self.filename_label.setStyleSheet("font-weight: bold;")

        grid = QGridLayout()
        self._tiles: dict[str, _Tile] = {}
        for i, (key, label) in enumerate(_TILES):
            tile = _Tile(key, label)
            tile.clicked.connect(self._on_tile_clicked)
            grid.addWidget(tile, i // 2, i % 2)
            self._tiles[key] = tile

        delete_btn = QPushButton("🗑 Supprimer la photo (Suppr)")
        delete_btn.setStyleSheet("QPushButton { color: white; background-color: #c0392b; padding: 6px; }")
        delete_btn.clicked.connect(self._on_delete_clicked)

        header = QHBoxLayout()
        header.addWidget(self.progress_label)
        header.addStretch()
        header.addWidget(self.filename_label)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addLayout(grid)
        layout.addWidget(delete_btn)

        QShortcut(QKeySequence(Qt.Key.Key_1), self, activated=lambda: self._choose("original"))
        QShortcut(QKeySequence(Qt.Key.Key_2), self, activated=lambda: self._choose("naturel"))
        QShortcut(QKeySequence(Qt.Key.Key_3), self, activated=lambda: self._choose("profondeur"))
        QShortcut(QKeySequence(Qt.Key.Key_4), self, activated=lambda: self._choose("macro"))
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, activated=self._on_delete_clicked)

    def show_photo(self, path: Path, rgb_thumb: np.ndarray, index: int, total: int) -> None:
        """Affiche une nouvelle photo (déjà décodée + réduite) avec ses 4 versions."""
        self._current_path = path
        self.progress_label.setText(f"Photo {index + 1} / {total}")
        self.filename_label.setText(path.name)

        self._tiles["original"].set_pixmap(_rgb_to_pixmap(rgb_thumb))
        for key, fn in PRESETS.items():
            result = fn(rgb_thumb)
            self._tiles[key].set_pixmap(_rgb_to_pixmap(result))

    def _on_tile_clicked(self, key: str) -> None:
        self._choose(key)

    def _on_delete_clicked(self) -> None:
        self._choose(None)

    def _choose(self, key: str | None) -> None:
        if self._current_path is None:
            return
        self.choice_made.emit(str(self._current_path), key)
