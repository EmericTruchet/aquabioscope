"""Dialogue de recadrage : cadre déplaçable/redimensionnable sur l'aperçu,
avec proportions imposables et grille des tiers."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from aquabioscope.imaging.crop import CropRect

# (libelle, rapport largeur/hauteur en pixels ; None = libre, 0 = celui de la photo)
RATIOS: list[tuple[str, float | None]] = [
    ("Libre", None),
    ("Proportions d'origine", 0),
    ("3:2", 3 / 2),
    ("4:3", 4 / 3),
    ("16:9", 16 / 9),
    ("1:1 (carré)", 1.0),
    ("4:5 (portrait)", 4 / 5),
    ("2:3 (portrait)", 2 / 3),
]
_HANDLE_PX = 10
_MIN_FRACTION = 0.05


def _rgb_to_pixmap(rgb: np.ndarray) -> QPixmap:
    rgb = np.ascontiguousarray(rgb)
    h, w, _ = rgb.shape
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class _CropCanvas(QWidget):
    """Affiche l'image et le cadre. Toutes les coordonnées du cadre sont en
    fractions de l'image ; la conversion en pixels écran se fait à
    l'affichage et à la souris."""

    def __init__(self, pixmap: QPixmap) -> None:
        super().__init__()
        self._pixmap = pixmap
        self._rect = QRectF(0, 0, 1, 1)
        self._ratio_n: float | None = None  # rapport w/h en fractions (None = libre)
        self._mode: str | None = None  # "move", "new" ou poignee : "tl", "t", "tr", "r", "br", "b", "bl", "l"
        self._press = QPointF()
        self._rect_at_press = QRectF()
        self.setMouseTracking(True)
        self.setMinimumSize(560, 400)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # --- etat ---------------------------------------------------------
    @property
    def image_aspect(self) -> float:
        return self._pixmap.width() / max(1, self._pixmap.height())

    def crop(self) -> CropRect:
        r = self._rect
        return CropRect(r.x(), r.y(), r.width(), r.height())

    def set_crop(self, crop: CropRect | None) -> None:
        self._rect = QRectF(0, 0, 1, 1) if crop is None else QRectF(crop.x, crop.y, crop.w, crop.h)
        self._enforce_ratio_centered()
        self.update()

    def set_ratio(self, pixel_ratio: float | None) -> None:
        """`pixel_ratio` : largeur/hauteur voulue en pixels (None = libre)."""
        self._ratio_n = None if pixel_ratio is None else pixel_ratio / self.image_aspect
        self._enforce_ratio_centered()
        self.update()

    def _enforce_ratio_centered(self) -> None:
        """Plus grand cadre aux bonnes proportions, centré sur le cadre actuel
        et contenu dans l'image."""
        if self._ratio_n is None:
            return
        c = self._rect.center()
        w = min(1.0, self._ratio_n)
        h = w / self._ratio_n
        if h > 1.0:
            h = 1.0
            w = h * self._ratio_n
        # ne pas agrandir au-dela du cadre courant si celui-ci est plus petit
        scale = min(1.0, max(self._rect.width() / w, self._rect.height() / h))
        w, h = w * scale, h * scale
        x = min(max(0.0, c.x() - w / 2), 1 - w)
        y = min(max(0.0, c.y() - h / 2), 1 - h)
        self._rect = QRectF(x, y, w, h)

    # --- geometrie ecran -----------------------------------------------
    def _image_rect(self) -> QRectF:
        pw, ph = self._pixmap.width(), self._pixmap.height()
        scale = min(self.width() / pw, self.height() / ph)
        w, h = pw * scale, ph * scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def _to_screen(self, r: QRectF) -> QRectF:
        img = self._image_rect()
        return QRectF(img.x() + r.x() * img.width(), img.y() + r.y() * img.height(),
                      r.width() * img.width(), r.height() * img.height())

    def _to_fraction(self, p: QPointF) -> QPointF:
        img = self._image_rect()
        return QPointF(
            min(1.0, max(0.0, (p.x() - img.x()) / img.width())),
            min(1.0, max(0.0, (p.y() - img.y()) / img.height())),
        )

    def _handles(self) -> dict[str, QPointF]:
        s = self._to_screen(self._rect)
        handles = {"tl": s.topLeft(), "tr": s.topRight(), "br": s.bottomRight(), "bl": s.bottomLeft()}
        if self._ratio_n is None:  # en proportions imposees, seuls les coins redimensionnent
            handles.update({
                "t": QPointF(s.center().x(), s.top()), "b": QPointF(s.center().x(), s.bottom()),
                "l": QPointF(s.left(), s.center().y()), "r": QPointF(s.right(), s.center().y()),
            })
        return handles

    def _hit(self, p: QPointF) -> str | None:
        for name, h in self._handles().items():
            if abs(p.x() - h.x()) <= _HANDLE_PX and abs(p.y() - h.y()) <= _HANDLE_PX:
                return name
        if self._to_screen(self._rect).contains(p):
            return "move"
        return None

    # --- dessin --------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        img = self._image_rect()
        painter.drawPixmap(img, self._pixmap, QRectF(self._pixmap.rect()))

        s = self._to_screen(self._rect)
        shade = QColor(0, 0, 0, 140)
        painter.fillRect(QRectF(img.left(), img.top(), img.width(), s.top() - img.top()), shade)
        painter.fillRect(QRectF(img.left(), s.bottom(), img.width(), img.bottom() - s.bottom()), shade)
        painter.fillRect(QRectF(img.left(), s.top(), s.left() - img.left(), s.height()), shade)
        painter.fillRect(QRectF(s.right(), s.top(), img.right() - s.right(), s.height()), shade)

        painter.setPen(QPen(QColor(255, 255, 255, 110), 1))
        for i in (1, 2):  # grille des tiers
            x = s.left() + s.width() * i / 3
            y = s.top() + s.height() * i / 3
            painter.drawLine(QPointF(x, s.top()), QPointF(x, s.bottom()))
            painter.drawLine(QPointF(s.left(), y), QPointF(s.right(), y))
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawRect(s)
        painter.setBrush(QColor(255, 255, 255))
        for h in self._handles().values():
            painter.drawRect(QRectF(h.x() - 4, h.y() - 4, 8, 8))

    # --- souris --------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        p = event.position()
        self._mode = self._hit(p) or "new"
        self._press = self._to_fraction(p)
        self._rect_at_press = QRectF(self._rect)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        p = event.position()
        if self._mode is None:
            hit = self._hit(p)
            cursors = {
                "move": Qt.CursorShape.SizeAllCursor,
                "tl": Qt.CursorShape.SizeFDiagCursor, "br": Qt.CursorShape.SizeFDiagCursor,
                "tr": Qt.CursorShape.SizeBDiagCursor, "bl": Qt.CursorShape.SizeBDiagCursor,
                "t": Qt.CursorShape.SizeVerCursor, "b": Qt.CursorShape.SizeVerCursor,
                "l": Qt.CursorShape.SizeHorCursor, "r": Qt.CursorShape.SizeHorCursor,
            }
            self.setCursor(cursors.get(hit, Qt.CursorShape.CrossCursor))
            return

        f = self._to_fraction(p)
        r0 = self._rect_at_press
        if self._mode == "move":
            dx, dy = f.x() - self._press.x(), f.y() - self._press.y()
            x = min(max(0.0, r0.x() + dx), 1 - r0.width())
            y = min(max(0.0, r0.y() + dy), 1 - r0.height())
            self._rect = QRectF(x, y, r0.width(), r0.height())
        elif self._mode == "new":
            self._rect = self._from_anchor(self._press, f) or self._rect
        elif self._mode in ("tl", "tr", "br", "bl"):
            opposite = {"tl": r0.bottomRight(), "tr": r0.bottomLeft(), "br": r0.topLeft(), "bl": r0.topRight()}
            self._rect = self._from_anchor(opposite[self._mode], f) or self._rect
        else:  # bord, mode libre uniquement
            left, top, right, bottom = r0.left(), r0.top(), r0.right(), r0.bottom()
            if self._mode == "l":
                left = min(f.x(), right - _MIN_FRACTION)
            elif self._mode == "r":
                right = max(f.x(), left + _MIN_FRACTION)
            elif self._mode == "t":
                top = min(f.y(), bottom - _MIN_FRACTION)
            else:
                bottom = max(f.y(), top + _MIN_FRACTION)
            self._rect = QRectF(QPointF(left, top), QPointF(right, bottom))
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._mode = None

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self._rect = QRectF(0, 0, 1, 1)
        self._enforce_ratio_centered()
        self.update()

    def _from_anchor(self, anchor: QPointF, f: QPointF) -> QRectF | None:
        """Cadre entre un coin fixe et la souris, en respectant les
        proportions imposées et les bords de l'image."""
        sx = 1 if f.x() >= anchor.x() else -1
        sy = 1 if f.y() >= anchor.y() else -1
        w, h = abs(f.x() - anchor.x()), abs(f.y() - anchor.y())
        max_w = 1 - anchor.x() if sx > 0 else anchor.x()
        max_h = 1 - anchor.y() if sy > 0 else anchor.y()
        if self._ratio_n is not None:
            if h == 0 or w / max(h, 1e-6) > self._ratio_n:
                h = w / self._ratio_n
            else:
                w = h * self._ratio_n
            if w > max_w:
                w, h = max_w, max_w / self._ratio_n
            if h > max_h:
                h, w = max_h, max_h * self._ratio_n
        else:
            w, h = min(w, max_w), min(h, max_h)
        if w < _MIN_FRACTION or h < _MIN_FRACTION:
            return None
        x = anchor.x() if sx > 0 else anchor.x() - w
        y = anchor.y() if sy > 0 else anchor.y() - h
        return QRectF(x, y, w, h)


class CropDialog(QDialog):
    """Renvoie le recadrage choisi dans `self.crop` (None = photo entière)."""

    def __init__(
        self, rgb_thumb: np.ndarray, initial: CropRect | None = None,
        previous: CropRect | None = None, parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Recadrer la photo")
        self.resize(980, 760)
        self.crop: CropRect | None = initial
        self._previous = previous

        self.canvas = _CropCanvas(_rgb_to_pixmap(rgb_thumb))
        self.canvas.set_crop(initial)

        self.ratio_combo = QComboBox()
        for label, _ in RATIOS:
            self.ratio_combo.addItem(label)
        self.ratio_combo.currentIndexChanged.connect(self._on_ratio_changed)

        previous_btn = QPushButton("↺  Comme la photo précédente")
        previous_btn.setObjectName("SecondaryButton")
        previous_btn.setEnabled(previous is not None)
        previous_btn.clicked.connect(lambda: self.canvas.set_crop(self._previous))

        reset_btn = QPushButton("Photo entière")
        reset_btn.setObjectName("SecondaryButton")
        reset_btn.clicked.connect(lambda: self.canvas.set_crop(None))

        top = QHBoxLayout()
        top.addWidget(QLabel("Proportions :"))
        top.addWidget(self.ratio_combo)
        top.addStretch()
        top.addWidget(previous_btn)
        top.addWidget(reset_btn)

        hint = QLabel(
            "Glisser dans le cadre pour le déplacer, sur les poignées pour le redimensionner, "
            "hors du cadre pour en tracer un nouveau  •  double-clic : photo entière"
        )
        hint.setObjectName("HintBar")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cancel_btn = QPushButton("Annuler")
        cancel_btn.setObjectName("SecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("Appliquer le recadrage")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._accept)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(cancel_btn)
        actions.addWidget(ok_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.canvas, stretch=1)
        layout.addWidget(hint)
        layout.addLayout(actions)

    def _on_ratio_changed(self, index: int) -> None:
        ratio = RATIOS[index][1]
        self.canvas.set_ratio(self.canvas.image_aspect if ratio == 0 else ratio)

    def _accept(self) -> None:
        crop = self.canvas.crop()
        self.crop = None if crop.is_full() else crop
        self.accept()
