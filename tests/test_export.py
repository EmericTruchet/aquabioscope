import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from divephoto.export import build_filename, draw_credit, export_photo, slugify


class ExportTest(unittest.TestCase):
    def test_slugify_strips_accents_and_specials(self) -> None:
        self.assertEqual(slugify("Cap de Creus !"), "cap-de-creus")
        self.assertEqual(slugify("Mérou brun"), "merou-brun")

    def test_build_filename_includes_site_species_and_date(self) -> None:
        name = build_filename("Cap de Creus", ["Mérou brun", "Sar commun"], date(2026, 9, 7), 3)
        self.assertEqual(name, "cap-de-creus_merou-brun-sar-commun_20260907_0003.jpg")

    def test_build_filename_without_species(self) -> None:
        name = build_filename("Cap de Creus", [], date(2026, 9, 7), 1)
        self.assertEqual(name, "cap-de-creus_20260907_0001.jpg")

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
            self.assertEqual(result.output_path.name, "cap-de-creus_merou-brun_20260907_0001.jpg")


if __name__ == "__main__":
    unittest.main()
