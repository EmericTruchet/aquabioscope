"""Dialogue de réglage manuel d'un preset "+" personnalisé (sliders + aperçu live)."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QSlider,
    QVBoxLayout, QWidget,
)

from divephoto.imaging.color import CustomPresetParams, apply_custom_preset


def _rgb_to_pixmap(rgb: np.ndarray) -> QPixmap:
    rgb = np.ascontiguousarray(rgb)
    h, w, _ = rgb.shape
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class _SliderRow(QWidget):
    def __init__(self, lo: int, hi: int, value: int, on_change) -> None:
        super().__init__()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(lo, hi)
        self.slider.setValue(value)
        self.value_label = QLabel(str(value))
        self.value_label.setFixedWidth(36)
        self.slider.valueChanged.connect(lambda v: (self.value_label.setText(str(v)), on_change()))

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.slider, stretch=1)
        row.addWidget(self.value_label)


class CustomPresetDialog(QDialog):
    """Ajuste un preset personnalise sur un apercu reduit ; renvoie les
    parametres choisis (`self.params`) si l'utilisateur valide."""

    def __init__(
        self,
        rgb_thumb: np.ndarray,
        initial: CustomPresetParams | None = None,
        initial_name: str = "",
        existing_names: tuple[str, ...] = (),
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nouveau preset personnalisé")
        self.resize(640, 660)

        self._rgb_thumb = rgb_thumb
        self.params = initial or CustomPresetParams()
        self.name = initial_name
        self._existing_names = {n for n in existing_names if n != initial_name}

        self.name_edit = QLineEdit(initial_name)
        self.name_edit.setPlaceholderText('Nom du preset, ex. "Épaves sombres"')

        self.preview = QLabel()
        self.preview.setObjectName("MainPreview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(480, 360)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(80)
        self._debounce.timeout.connect(self._recompute)

        def schedule():
            self._debounce.start()

        self.row_red = _SliderRow(0, 200, int(self.params.red_strength * 100), schedule)
        self.row_gray = _SliderRow(0, 100, int(self.params.gray_balance * 100), schedule)
        self.row_contrast = _SliderRow(0, 400, int(self.params.contrast * 100), schedule)
        self.row_sharpen = _SliderRow(0, 100, int(self.params.sharpen * 100), schedule)
        self.row_saturation = _SliderRow(50, 200, int(self.params.saturation * 100), schedule)

        form = QFormLayout()
        form.addRow("Correction rouge/bleu", self.row_red)
        form.addRow("Rééquilibrage global", self.row_gray)
        form.addRow("Contraste local", self.row_contrast)
        form.addRow("Netteté", self.row_sharpen)
        form.addRow("Saturation", self.row_saturation)

        buttons = QDialogButtonBox()
        cancel_btn = buttons.addButton("Annuler", QDialogButtonBox.ButtonRole.RejectRole)
        reset_btn = buttons.addButton("Réinitialiser", QDialogButtonBox.ButtonRole.ResetRole)
        apply_btn = buttons.addButton("Appliquer", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn.clicked.connect(self.reject)
        apply_btn.clicked.connect(self._on_apply)
        reset_btn.clicked.connect(self._on_reset)

        form.insertRow(0, "Nom du preset", self.name_edit)

        layout = QVBoxLayout(self)
        layout.addWidget(self.preview, stretch=1)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._recompute()

    def _current_params(self) -> CustomPresetParams:
        return CustomPresetParams(
            red_strength=self.row_red.slider.value() / 100,
            gray_balance=self.row_gray.slider.value() / 100,
            contrast=self.row_contrast.slider.value() / 100,
            sharpen=self.row_sharpen.slider.value() / 100,
            saturation=self.row_saturation.slider.value() / 100,
        )

    def _recompute(self) -> None:
        params = self._current_params()
        result = apply_custom_preset(self._rgb_thumb, params)
        pixmap = _rgb_to_pixmap(result).scaled(
            self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.preview.setPixmap(pixmap)

    def _on_reset(self) -> None:
        defaults = CustomPresetParams()
        self.row_red.slider.setValue(int(defaults.red_strength * 100))
        self.row_gray.slider.setValue(int(defaults.gray_balance * 100))
        self.row_contrast.slider.setValue(int(defaults.contrast * 100))
        self.row_sharpen.slider.setValue(int(defaults.sharpen * 100))
        self.row_saturation.slider.setValue(int(defaults.saturation * 100))

    def _on_apply(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Nom manquant", "Merci de donner un nom à ce preset.")
            return
        if name in self._existing_names:
            QMessageBox.warning(self, "Nom déjà utilisé", f"Un preset nommé « {name} » existe déjà.")
            return
        self.name = name
        self.params = self._current_params()
        self.accept()
