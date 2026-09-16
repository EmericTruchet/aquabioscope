import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from aquabioscope.custom_presets_store import load_named_presets, save_named_presets
from aquabioscope.imaging.color import CustomPresetParams


class CustomPresetsStoreTest(unittest.TestCase):
    def test_round_trip(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "custom_presets.json"
            presets = {
                "Epaves sombres": CustomPresetParams(red_strength=1.4, contrast=2.8, saturation=1.4),
                "Macro doux": CustomPresetParams(sharpen=0.2),
            }
            save_named_presets(presets, path)
            loaded = load_named_presets(path)
            self.assertEqual(set(loaded), set(presets))
            self.assertEqual(loaded["Epaves sombres"], presets["Epaves sombres"])
            self.assertEqual(loaded["Macro doux"], presets["Macro doux"])

    def test_missing_file_returns_empty_dict(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "does_not_exist.json"
            self.assertEqual(load_named_presets(path), {})

    def test_corrupt_file_returns_empty_dict(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "custom_presets.json"
            path.write_text("not valid json {{{", encoding="utf-8")
            self.assertEqual(load_named_presets(path), {})


if __name__ == "__main__":
    unittest.main()
