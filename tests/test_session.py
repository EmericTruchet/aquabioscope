import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from aquabioscope.session import DiveSession


class DiveSessionTest(unittest.TestCase):
    def test_scan_photos_filters_supported_extensions(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.jpg").write_bytes(b"")
            (tmp_path / "b.CR2").write_bytes(b"")
            (tmp_path / "notes.txt").write_bytes(b"")

            session = DiveSession(
                input_dir=tmp_path,
                output_dir=tmp_path / "out",
                dive_site="Cap de Creus",
                dive_date=date(2026, 6, 12),
                photographer="Emeric Truchet",
            )
            names = sorted(p.name for p in session.scan_photos())
            self.assertEqual(names, ["a.jpg", "b.CR2"])

    def test_credit_text(self) -> None:
        session = DiveSession(
            input_dir=Path("in"),
            output_dir=Path("out"),
            dive_site="Cap de Creus",
            dive_date=date(2026, 6, 12),
            photographer="Emeric Truchet",
        )
        self.assertEqual(session.credit_text, "Cap de Creus 2026 © Emeric Truchet")


if __name__ == "__main__":
    unittest.main()
