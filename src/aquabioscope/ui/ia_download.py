"""Installation du module IA à la demande (premier usage des suggestions IA)."""
from __future__ import annotations

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QWidget

from aquabioscope import identify


class _ModelDownloadWorker(QThread):
    progress = Signal(int, int)
    done = Signal()
    failed = Signal(str)

    def run(self) -> None:
        try:
            identify.download_model(
                progress=lambda r, t: self.progress.emit(r, t), cancelled=self.isInterruptionRequested,
            )
        except OSError as exc:
            self.failed.emit(str(exc))
            return
        self.done.emit()


def ensure_model_installed(parent: QWidget) -> bool:
    """Propose de télécharger le module IA s'il manque ; renvoie True s'il
    est (désormais) installé."""
    if identify.is_installed():
        return True
    if identify.old_models():
        message = (
            "Cette version d'AquaBioScope utilise un nouveau module IA, plus performant "
            f"({identify.MODEL_SIZE_LABEL} à télécharger une fois). L'ancien sera supprimé.\n\n"
            "Télécharger maintenant ?"
        )
    else:
        message = (
            "Les suggestions IA ont besoin d'un module à télécharger une seule fois "
            f"({identify.MODEL_SIZE_LABEL}). Il fonctionne ensuite sans connexion, "
            "directement sur cet ordinateur.\n\nTélécharger maintenant ?"
        )
    reply = QMessageBox.question(parent, "Suggestions d'espèces par IA", message)
    if reply != QMessageBox.StandardButton.Yes:
        return False

    dialog = QProgressDialog("Téléchargement du module IA…", "Annuler", 0, 100, parent)
    dialog.setWindowTitle("Suggestions d'espèces par IA")
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setMinimumDuration(0)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)
    dialog.setValue(0)

    worker = _ModelDownloadWorker(parent)
    outcome: dict[str, str | bool] = {}

    def on_progress(received: int, total: int) -> None:
        if total:
            dialog.setValue(received * 100 // total)
            dialog.setLabelText(f"Téléchargement du module IA… {received // 1_000_000} / {total // 1_000_000} Mo")

    def on_done() -> None:
        outcome["ok"] = True
        dialog.accept()

    def on_failed(message: str) -> None:
        outcome["error"] = message
        dialog.cancel()

    worker.progress.connect(on_progress)
    worker.done.connect(on_done)
    worker.failed.connect(on_failed)
    worker.start()
    dialog.exec()
    if not outcome:  # annule par l'utilisateur
        worker.requestInterruption()
        worker.wait()
        return False
    worker.wait()
    if "error" in outcome:
        QMessageBox.warning(
            parent, "Module IA indisponible",
            f"Le module IA n'a pas pu être téléchargé ({outcome['error']}).\n"
            "La session continue sans suggestions IA.",
        )
        return False
    return True
