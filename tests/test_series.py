import os
import struct
import unittest
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import numpy as np
import piexif
from PIL import Image

from aquabioscope import series

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _write_jpeg(path: Path, color: tuple[int, int, int], taken: datetime, pattern: int = 0) -> None:
    rgb = np.zeros((120, 160, 3), dtype=np.uint8)
    rgb[:] = color
    rgb[30 + pattern:70 + pattern, 40:100] = (240, 240, 240)  # le "sujet"
    exif = piexif.dump({"Exif": {piexif.ExifIFD.DateTimeOriginal: taken.strftime("%Y:%m:%d %H:%M:%S").encode()}})
    Image.fromarray(rgb).save(path, exif=exif, quality=90)


def _orf_like(taken: str) -> bytes:
    """En-tête TIFF à la mode Olympus ("IIRO") avec un IFD EXIF minimal."""
    value = taken.encode() + b"\x00"
    ifd0_offset = 8
    exif_offset = ifd0_offset + 2 + 12 + 4
    value_offset = exif_offset + 2 + 12 + 4
    data = b"IIRO" + struct.pack("<I", ifd0_offset)
    data += struct.pack("<H", 1) + struct.pack("<HHII", 0x8769, 4, 1, exif_offset) + struct.pack("<I", 0)
    data += struct.pack("<H", 1) + struct.pack("<HHII", 0x9003, 2, len(value), value_offset) + struct.pack("<I", 0)
    return data + value


class CaptureTimeTest(unittest.TestCase):
    def test_reads_raw_with_non_standard_tiff_header(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "PA180187.ORF"
            path.write_bytes(_orf_like("2026:10:18 21:44:24"))
            self.assertEqual(series.capture_time(path), datetime(2026, 10, 18, 21, 44, 24).timestamp())

    def test_reads_jpeg_exif(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.jpg"
            _write_jpeg(path, (20, 60, 140), datetime(2026, 6, 12, 10, 0, 5))
            self.assertEqual(series.capture_time(path), datetime(2026, 6, 12, 10, 0, 5).timestamp())

    def test_unreadable_file_gives_none(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.orf"
            path.write_bytes(b"pas une image")
            self.assertIsNone(series.capture_time(path))


class SeriesCandidatesTest(unittest.TestCase):
    def test_chain_stops_at_a_long_gap(self) -> None:
        times = [0.0, 3.0, 10.0, 25.0, 300.0, 302.0]
        self.assertEqual(series.series_candidates(times, 0), [1, 2, 3])
        self.assertEqual(series.series_candidates(times, 4), [5])
        self.assertEqual(series.series_candidates(times, 3), [])

    def test_unknown_time_breaks_the_series(self) -> None:
        self.assertEqual(series.series_candidates([0.0, 2.0, None, 4.0], 0), [1])

    def test_similarity_separates_different_scenes(self) -> None:
        rng = np.random.default_rng(0)
        base = rng.integers(0, 255, (200, 300, 3)).astype(np.uint8)
        shifted = np.roll(base, 2, axis=1)
        other = np.full_like(base, (200, 90, 30))
        sig = series.signature(base)
        self.assertGreater(series.similarity(sig, series.signature(shifted)), series.SIMILARITY_THRESHOLD)
        self.assertLess(series.similarity(sig, series.signature(other)), series.SIMILARITY_THRESHOLD)


class NavigationFlowTest(unittest.TestCase):
    """Parcours complet dans la fenêtre principale (sans affichage)."""

    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from aquabioscope import app as app_module
        from aquabioscope.session import DiveSession

        self.tmp = TemporaryDirectory()
        folder = Path(self.tmp.name)
        start = datetime(2026, 6, 12, 10, 0, 0)
        # 0 seule ; 1-2-3 rafale sur le meme sujet ; 4 dix minutes plus tard
        shots = [(0, (20, 60, 140)), (60, (150, 80, 40)), (63, (150, 80, 40)), (66, (150, 80, 40)), (666, (20, 120, 60))]
        for n, (offset, color) in enumerate(shots):
            _write_jpeg(folder / f"P{n}.jpg", color, start.replace(minute=offset // 60, second=offset % 60), pattern=n)
        patcher = mock.patch("aquabioscope.ui.review.load_named_presets", return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.window = app_module.MainWindow()
        self.window._start_export = mock.Mock()
        self.window._on_session_ready(DiveSession(folder, folder / "out", "Cap de Creus", date(2026, 6, 12), "Moi"))
        self.review = self.window.review
        self.tags = self.window.species_tag_widget

    def tearDown(self) -> None:
        self.window.deleteLater()
        self.tmp.cleanup()

    def _entry(self, name: str):
        from aquabioscope.species import SpeciesEntry

        return SpeciesEntry(embranchement="Mollusque", nom_vernaculaire=name, nom_scientifique="", regions=())

    def _tag(self, *names: str) -> None:
        self.tags._selected = [self._entry(n) for n in names]
        self.tags._confirm()

    def test_back_reopens_previous_photo_with_its_choices(self) -> None:
        self.review._select("macro")
        self.review._confirm()
        self._tag("Poulpe")
        self.assertEqual(self.window.current_index, 1)

        self.review._go_previous()
        self.assertEqual(self.window.current_index, 0)
        self.assertEqual(self.review.selected_key, "macro")
        self.review._select("vert")
        self.review._confirm()
        self.assertEqual([e.nom_vernaculaire for e in self.tags._selected], ["Poulpe"])
        self._tag("Poulpe", "Girelle")

        self.assertEqual(self.window.current_index, 1)  # on reprend la ou on en etait
        self.assertEqual(self.window.choices[str(self.window.photos[0])], "vert")
        self.assertEqual(len(self.window.species_tags[str(self.window.photos[0])]), 2)

    def test_deleted_photo_can_be_recovered(self) -> None:
        self.review._delete()
        self.review._go_previous()
        self.assertTrue(self.review.state_badge.isVisibleTo(self.review))
        self.review._confirm()
        self._tag("Mérou brun")
        self.assertIsNotNone(self.window.choices[str(self.window.photos[0])])
        self.assertIn(str(self.window.photos[0]), self.window.species_tags)

    def test_series_applies_choices_and_species_to_checked_photos(self) -> None:
        self.review._confirm()
        self._tag("Tourteau")
        self.assertEqual(self.window.current_index, 1)
        self.assertTrue(self.review.series_btn.isVisibleTo(self.review))
        self.assertIn("(3)", self.review.series_btn.text())

        self.review._select("profondeur")
        with mock.patch("aquabioscope.app.SeriesDialog") as dialog_cls:
            dialog = dialog_cls.return_value
            dialog.exec.return_value = dialog_cls.DialogCode.Accepted
            dialog.selected_indices = [3]  # la photo 2 est decochee
            self.review._confirm_series()
            tiles = dialog_cls.call_args.args[1]
        self.assertEqual([t[0] for t in tiles], [2, 3])
        self.assertEqual([t[3] for t in tiles], [True, True])  # meme sujet : cochees par defaut (vrais bool, pour Qt)
        self.assertTrue(all(type(t[3]) is bool for t in tiles))
        self.assertTrue(self.tags.series_note.isVisibleTo(self.tags))
        self._tag("Nudibranche")

        photos = [str(p) for p in self.window.photos]
        self.assertEqual(self.window.choices[photos[3]], "profondeur")
        self.assertEqual([e.nom_vernaculaire for e in self.window.species_tags[photos[3]]], ["Nudibranche"])
        self.assertNotIn(photos[2], self.window.choices)
        self.assertEqual(self.window.current_index, 2)  # la photo decochee reste a traiter
        self.assertFalse(self.review.series_btn.isVisibleTo(self.review))  # la suivante est deja faite

        self.review._confirm()
        self._tag()
        self.assertEqual(self.window.current_index, 4)
        self.review._confirm()
        self._tag()
        # derniere photo validee : recapitulatif, pas d'export automatique
        self.window._start_export.assert_not_called()
        self.assertIs(self.window.stack.currentWidget(), self.window.ready_to_export)
        self.assertIn("5 photos retenues", self.window.ready_to_export.summary_label.text())
        self.assertIn("2 espèces différentes", self.window.ready_to_export.summary_label.text())
        self.assertIn("2 photos retenues sans espèce", self.window.ready_to_export.warning_label.text())

    def test_ready_screen_allows_going_back_before_export(self) -> None:
        for _ in self.window.photos:
            self.review._confirm()
            self._tag("Saupe")
        self.assertIs(self.window.stack.currentWidget(), self.window.ready_to_export)
        self.window.ready_to_export.back_requested.emit()
        self.assertIs(self.window.stack.currentWidget(), self.review)
        self.assertEqual(self.window.current_index, 4)
        self.assertTrue(self.review.state_badge.isVisibleTo(self.review))  # deja validee
        self.review._go_previous()
        self.review._delete()
        self.assertIs(self.window.stack.currentWidget(), self.window.ready_to_export)
        self.assertIn("1 écartée", self.window.ready_to_export.summary_label.text())
        self.window.ready_to_export.export_btn.click()
        self.window._start_export.assert_called_once()


if __name__ == "__main__":
    unittest.main()
