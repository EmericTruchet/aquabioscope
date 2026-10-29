"""Bandeau "nouvelle version disponible", affiché en haut de la fenêtre.

La vérification se fait en tâche de fond au démarrage (sans jamais bloquer
ni gêner l'utilisation si le réseau est absent). Le bouton ouvre les
nouveautés de la version (note de la Release GitHub, tirée de
NOUVEAUTES.md) ; selon le mode d'installation (voir aquabioscope.updater),
on installe ensuite la mise à jour directement ou on ouvre la page de
téléchargement.

L'installation est silencieuse : entre la fermeture et le redémarrage
automatique, rien ne s'affiche pendant une minute environ. On le dit donc
clairement avant de lancer, puis juste avant de fermer, pour que personne
ne croie à un plantage et ne relance l'application à la main.
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTextBrowser,
    QVBoxLayout, QWidget,
)

from aquabioscope import updater

INSTALL_STEPS = (
    "<b>Comment ça se passe :</b> clique sur « Installer la mise à jour », puis <b>patiente</b>. "
    "AquaBioScope télécharge la nouvelle version, se ferme, s'installe et <b>redémarre tout seul</b> "
    "(environ une minute pendant laquelle rien ne s'affiche) : ne le relance pas toi-même.<br>"
    "Une session en cours (photos pas encore exportées) serait perdue : termine-la d'abord si besoin."
)
PROGRESS_SUFFIX = "(AquaBioScope redémarrera tout seul ensuite)"


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


class ReleaseNotesDialog(QDialog):
    """Nouveautés de la version, puis installation (ou téléchargement)."""

    def __init__(self, info: updater.UpdateInfo, can_install: bool, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"AquaBioScope {info.version}")
        self.resize(620, 520)

        title = QLabel(f"Nouveautés de la version {info.version}")
        title.setObjectName("Subtitle")
        self.notes = QTextBrowser()
        self.notes.setOpenExternalLinks(True)
        if info.notes:
            self.notes.setMarkdown(info.notes)
        else:
            self.notes.setPlainText("Pas de détail pour cette version : voir la page de téléchargement.")
        steps = QLabel(INSTALL_STEPS if can_install else
                       "Le bouton ouvre la page de téléchargement de la nouvelle version.")
        steps.setWordWrap(True)
        steps.setTextFormat(Qt.TextFormat.RichText)

        buttons = QDialogButtonBox()
        ok = buttons.addButton(
            "Installer la mise à jour" if can_install else "Télécharger", QDialogButtonBox.ButtonRole.AcceptRole,
        )
        later = buttons.addButton("Plus tard", QDialogButtonBox.ButtonRole.RejectRole)
        later.setObjectName("SecondaryButton")
        ok.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.notes, stretch=1)
        layout.addWidget(steps)
        layout.addWidget(buttons)


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
        self.action_btn.setText(
            "Voir les nouveautés et mettre à jour" if self._can_install else "Voir les nouveautés et télécharger"
        )
        self.show()

    def _on_action(self) -> None:
        if self._info is None:
            return
        dialog = ReleaseNotesDialog(self._info, self._can_install, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not self._can_install:
            QDesktopServices.openUrl(QUrl(self._info.page_url))
            self.hide()
            return
        self.action_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.label.setText(f"Téléchargement de la mise à jour…  {PROGRESS_SUFFIX}")
        self._download_worker = _DownloadWorker(self._info.installer_url)
        self._download_worker.progress.connect(self._on_progress)
        self._download_worker.done.connect(self._on_downloaded)
        self._download_worker.failed.connect(self._on_failed)
        self._download_worker.start()

    def _on_progress(self, received: int, total: int) -> None:
        if total:
            self.label.setText(f"Téléchargement de la mise à jour… {received * 100 // total} %  {PROGRESS_SUFFIX}")

    def _on_downloaded(self, path: str) -> None:
        self.label.setText("Installation de la mise à jour, AquaBioScope va redémarrer…")
        QMessageBox.information(
            self, "Mise à jour prête",
            "AquaBioScope va maintenant se fermer, s'installer et redémarrer tout seul.\n\n"
            "Patiente environ une minute : rien ne s'affiche pendant l'installation, c'est normal. "
            "Ne relance pas AquaBioScope toi-même.",
        )
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
