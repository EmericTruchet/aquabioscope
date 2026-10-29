"""Dialogue « Identifier une zone » : on encadre un sujet de la photo (une
deuxième espèce, un animal trop petit dans le cadre…) pour que l'IA ne
regarde que lui. Même cadre que le dialogue de recadrage, sans proportions."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from aquabioscope.imaging.crop import CropRect
from aquabioscope.ui.crop_dialog import _CropCanvas, _rgb_to_pixmap


class ZoneDialog(QDialog):
    """Renvoie la zone choisie dans `self.zone` (None = photo entière)."""

    def __init__(self, rgb: np.ndarray, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Identifier une zone")
        self.resize(980, 760)
        self.zone: CropRect | None = None

        self.canvas = _CropCanvas(_rgb_to_pixmap(rgb))
        # cadre de depart au centre : le plus souvent on vise un sujet, pas toute la photo
        self.canvas.set_crop(CropRect(0.3, 0.3, 0.4, 0.4))

        title = QLabel("Encadre le sujet à identifier : l'IA ne regardera que cette zone.")
        title.setObjectName("Subtitle")
        hint = QLabel(
            "Tracer un cadre hors du cadre actuel, glisser pour le déplacer, poignées pour le redimensionner. "
            "Un cadre serré autour du sujet donne de meilleures suggestions."
        )
        hint.setObjectName("HintBar")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cancel_btn = QPushButton("Annuler")
        cancel_btn.setObjectName("SecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("Identifier cette zone")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._accept)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(cancel_btn)
        actions.addWidget(ok_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.canvas, stretch=1)
        layout.addWidget(hint)
        layout.addLayout(actions)

    def _accept(self) -> None:
        zone = self.canvas.crop()
        self.zone = None if zone.is_full() else zone
        self.accept()
