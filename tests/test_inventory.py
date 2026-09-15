import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import openpyxl

from divephoto.inventory import unique_sorted_species, write_inventory_xlsx
from divephoto.species import SpeciesEntry


class InventoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.merou = SpeciesEntry("Poissons osseux", "Mérou brun", "Epinephelus marginatus", ("mediterranee",))
        self.sar = SpeciesEntry("Poissons osseux", "Sar commun", "Diplodus sargus", ("mediterranee",))
        self.anemone = SpeciesEntry("Cnidaire", "Anémone verte", "Anemonia viridis", ("mediterranee",))

    def test_unique_sorted_species_dedupes_and_orders_by_embranchement(self) -> None:
        all_tags = [[self.merou, self.anemone], [self.merou], [self.sar]]
        result = unique_sorted_species(all_tags)
        self.assertEqual(len(result), 3)
        # Cnidaire vient avant Poissons osseux dans EMBRANCHEMENT_ORDER
        self.assertEqual(result[0].embranchement, "Cnidaire")
        names = [e.nom_vernaculaire for e in result[1:]]
        self.assertEqual(names, ["Mérou brun", "Sar commun"])

    def test_write_inventory_xlsx_matches_reference_format(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "inventaire.xlsx"
            write_inventory_xlsx(path, [self.anemone, self.merou])

            wb = openpyxl.load_workbook(path)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            self.assertEqual(rows[0], ("Embranchement", "Nom français", "Nom latin"))
            self.assertEqual(rows[1], ("Cnidaire", "Anémone verte", "Anemonia viridis"))
            self.assertEqual(rows[2], ("Poissons osseux", "Mérou brun", "Epinephelus marginatus"))


if __name__ == "__main__":
    unittest.main()
