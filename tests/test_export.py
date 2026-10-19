import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

import piexif
from PIL import Image

from aquabioscope.export import build_exif_bytes, build_filename, draw_credit, export_photo, slugify


class ExportTest(unittest.TestCase):
    def test_slugify_strips_accents_and_specials(self) -> None:
        self.assertEqual(slugify("Cap de Creus !"), "Cap-de-creus")
        self.assertEqual(slugify("Mérou brun"), "Merou-brun")

    def test_build_filename_puts_species_first_then_site(self) -> None:
        name = build_filename("Cap de Creus", ["Mérou brun", "Sar commun"], date(2026, 9, 7), 3)
        self.assertEqual(name, "Merou-brun_Sar-commun_Cap-de-creus_20260907_0003.jpg")

    def test_build_filename_without_species(self) -> None:
        name = build_filename("Cap de Creus", [], date(2026, 9, 7), 1)
        self.assertEqual(name, "Cap-de-creus_20260907_0001.jpg")

    def test_draw_credit_returns_same_shape(self) -> None:
        rgb = np.zeros((200, 300, 3), dtype=np.uint8)
        out = draw_credit(rgb, "Cap de Creus 2026 © Test")
        self.assertEqual(out.shape, rgb.shape)
        self.assertEqual(out.dtype, rgb.dtype)
        # du texte blanc a ete dessine quelque part
        self.assertTrue((out > 0).any())

    def test_export_photo_writes_file_with_expected_name(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.jpg"
            source.write_bytes(b"not a real jpeg, only used for exif fallback path")
            rgb = (np.random.default_rng(0).uniform(0, 255, (60, 80, 3))).astype(np.uint8)

            result = export_photo(
                source_path=source,
                output_dir=tmp_path,
                rgb_full=rgb,
                preset_fn=None,
                dive_site="Cap de Creus",
                dive_date=date(2026, 9, 7),
                photographer="Emeric Truchet",
                species_names=["Mérou brun"],
                seq=1,
            )
            self.assertTrue(result.output_path.exists())
            self.assertEqual(result.output_path.name, "Merou-brun_Cap-de-creus_20260907_0001.jpg")

    def test_exif_with_huge_maker_note_still_fits_in_a_jpeg(self) -> None:
        # Certains appareils (Olympus TG) ecrivent des notes constructeur
        # proches de la limite du segment EXIF d'un JPEG (64 Ko) : l'ajout des
        # mots-cles especes la faisait depasser.
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.jpg"
            exif = {"0th": {piexif.ImageIFD.Model: b"TG-6"}, "Exif": {piexif.ExifIFD.MakerNote: b"x" * 65440},
                    "GPS": {}, "1st": {}}
            Image.new("RGB", (8, 8)).save(source, exif=piexif.dump(exif))
            exif_bytes = build_exif_bytes(source, "Riou", ["Chapon"])
            Image.new("RGB", (8, 8)).save(Path(tmp) / "out.jpg", exif=exif_bytes)  # levait "EXIF data is too long"
            self.assertEqual(piexif.load(exif_bytes)["0th"][piexif.ImageIFD.Model], b"TG-6")


if __name__ == "__main__":
    unittest.main()
