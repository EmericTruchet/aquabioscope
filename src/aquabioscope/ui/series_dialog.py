"""Dialogue « Appliquer à la série » : montre les photos prises juste après
celle en cours, avec la correction et le recadrage choisis, pour cocher
celles qui recevront les mêmes réglages et les mêmes espèces. Les photos
qui ne ressemblent pas assez à la précédente sont proposées décochées."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

_TILE_W, _TILE_H = 220, 165
_COLUMNS = 4


def _rgb_to_pixmap(rgb: np.ndarray) -> QPixmap:
    rgb = np.ascontiguousarray(rgb)
    h, w, _ = rgb.shape
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class _SeriesTile(QWidget):
    def __init__(self, path: Path, rgb: np.ndarray, checked: bool | None) -> None:
        """`checked` à None : photo en cours, toujours incluse."""
        super().__init__()
        self.setObjectName("GalleryThumb")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("selected", "true" if checked is None else "false")

        image = QLabel()
        image.setFixedSize(_TILE_W, _TILE_H)
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setPixmap(_rgb_to_pixmap(rgb).scaled(
            image.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        ))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(image)
        if checked is None:
            self.checkbox = None
            caption = QLabel(f"{path.name} (photo en cours)")
            caption.setObjectName("ThumbCaption")
            layout.addWidget(caption)
        else:
            self.checkbox = QCheckBox(path.name)
            self.checkbox.setChecked(checked)
            layout.addWidget(self.checkbox)
            image.mousePressEvent = lambda _e: self.checkbox.toggle()
            image.setCursor(Qt.CursorShape.PointingHandCursor)


class SeriesDialog(QDialog):
    def __init__(
        self, current: tuple[Path, np.ndarray], candidates: list[tuple[int, Path, np.ndarray, bool]],
        parent: QWidget | None = None,
    ) -> None:
        """`candidates` : (indice, chemin, aperçu déjà corrigé, coché par défaut)."""
        super().__init__(parent)
        self.setWindowTitle("Appliquer à la série")
        self._indices = [index for index, _path, _rgb, _checked in candidates]

        intro = QLabel(
            "Ces photos ont été prises juste après celle-ci. Les photos cochées recevront la même correction, "
            "le même recadrage et les mêmes espèces. Tu pourras toujours revenir sur l'une d'elles "
            "avec « ← Photo précédente »."
        )
        intro.setWordWrap(True)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setSpacing(10)
        self._tiles = [_SeriesTile(current[0], current[1], None)]
        self._tiles += [_SeriesTile(path, rgb, checked) for _i, path, rgb, checked in candidates]
        for n, tile in enumerate(self._tiles):
            grid.addWidget(tile, n // _COLUMNS, n % _COLUMNS)
            if tile.checkbox is not None:
                tile.checkbox.toggled.connect(self._update_button)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(grid_host)
        columns = min(len(self._tiles), _COLUMNS)
        rows = min(2, 1 + (len(self._tiles) - 1) // _COLUMNS)  # au-dela de 2 rangees : defilement
        scroll.setMinimumHeight(rows * (_TILE_H + 56) + 16)
        self.resize(columns * (_TILE_W + 28) + 60, rows * (_TILE_H + 56) + 170)

        all_btn = QPushButton("Tout cocher")
        all_btn.setObjectName("SecondaryButton")
        all_btn.clicked.connect(lambda: self._set_all(True))
        none_btn = QPushButton("Tout décocher")
        none_btn.setObjectName("SecondaryButton")
        none_btn.clicked.connect(lambda: self._set_all(False))
        cancel_btn = QPushButton("Annuler")
        cancel_btn.setObjectName("SecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        self.apply_btn = QPushButton()
        self.apply_btn.clicked.connect(self.accept)
        self.apply_btn.setDefault(True)

        buttons = QHBoxLayout()
        buttons.addWidget(all_btn)
        buttons.addWidget(none_btn)
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        buttons.addWidget(self.apply_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(scroll, stretch=1)
        layout.addLayout(buttons)
        self._update_button()

    def _set_all(self, checked: bool) -> None:
        for tile in self._tiles[1:]:
            tile.checkbox.setChecked(checked)

    def _update_button(self) -> None:
        count = 1 + len(self.selected_indices)
        self.apply_btn.setText(f"Appliquer à {count} photo{'s' if count > 1 else ''}  →")

    @property
    def selected_indices(self) -> list[int]:
        return [index for index, tile in zip(self._indices, self._tiles[1:]) if tile.checkbox.isChecked()]
