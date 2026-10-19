"""Bandeau "nouvelle version disponible", affiché en haut de la fenêtre.

La vérification se fait en tâche de fond au démarrage (sans jamais bloquer
ni gêner l'utilisation si le réseau est absent). Selon le mode
d'installation (voir aquabioscope.updater), le bouton installe la mise à
jour directement ou ouvre la page de téléchargement.
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMessageBox, QPushButton, QWidget

from aquabioscope import updater


class _CheckWorker(QThread):
    found = Signal(object)  # UpdateInfo

    def run(self) -> None:
        info = updater.check_for_update()
        if info is not None:
            self.found.emit(info)


class _DownloadWorker(QThread):
    progress = Signal(int, int)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url

    def run(self) -> None:
        try:
            path = updater.download_installer(self._url, progress=lambda r, t: self.progress.emit(r, t))
        except OSError as exc:
            self.failed.emit(str(exc))
            return
        self.done.emit(str(path))


class UpdateBanner(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("UpdateBanner")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.hide()
        self._info: updater.UpdateInfo | None = None
        self._can_install = False

        self.label = QLabel()
        self.action_btn = QPushButton()
        self.action_btn.clicked.connect(self._on_action)
        self.later_btn = QPushButton("Plus tard")
        self.later_btn.setObjectName("SecondaryButton")
        self.later_btn.clicked.connect(self.hide)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.addWidget(self.label, stretch=1)
        layout.addWidget(self.later_btn)
        layout.addWidget(self.action_btn)

        self._check_worker = _CheckWorker(self)
        self._check_worker.found.connect(self._on_update_found)
        self._download_worker: _DownloadWorker | None = None

    def start_check(self) -> None:
        self._check_worker.start()

    def _on_update_found(self, info: updater.UpdateInfo) -> None:
        self._info = info
        self._can_install = updater.install_kind() is updater.InstallKind.INSTALLER and bool(info.installer_url)
        self.label.setText(f"🎉  Nouvelle version {info.version} d'AquaBioScope disponible.")
        self.action_btn.setText("Mettre à jour maintenant" if self._can_install else "Télécharger")
        self.show()

    def _on_action(self) -> None:
        if self._info is None:
            return
        if not self._can_install:
            QDesktopServices.openUrl(QUrl(self._info.page_url))
            self.hide()
            return
        reply = QMessageBox.question(
            self, "Mettre à jour AquaBioScope",
            f"AquaBioScope va télécharger la version {self._info.version}, se fermer, "
            "s'installer puis redémarrer tout seul.\n\n"
            "Une session en cours (photos pas encore exportées) serait perdue. Continuer ?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.action_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.label.setText("Téléchargement de la mise à jour…")
        self._download_worker = _DownloadWorker(self._info.installer_url)
        self._download_worker.progress.connect(self._on_progress)
        self._download_worker.done.connect(self._on_downloaded)
        self._download_worker.failed.connect(self._on_failed)
        self._download_worker.start()

    def _on_progress(self, received: int, total: int) -> None:
        if total:
            self.label.setText(f"Téléchargement de la mise à jour… {received * 100 // total} %")

    def _on_downloaded(self, path: str) -> None:
        self.label.setText("Installation de la mise à jour, AquaBioScope va redémarrer…")
        try:
            updater.launch_silent_install(path)
        except OSError as exc:
            self._on_failed(str(exc))
            return
        QApplication.quit()

    def _on_failed(self, message: str) -> None:
        QMessageBox.warning(
            self, "Mise à jour impossible",
            f"La mise à jour n'a pas pu être téléchargée ({message}).\n"
            "Tu peux la télécharger à la main depuis la page qui va s'ouvrir.",
        )
        QDesktopServices.openUrl(QUrl(self._info.page_url))
        self.hide()
