import unittest

from divephoto.species import EMBRANCHEMENT_ORDER, SpeciesCatalog, SpeciesEntry, load_species


class SpeciesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.entries = load_species()
        self.catalog = SpeciesCatalog(self.entries)

    def test_loads_entries_covering_all_embranchements(self) -> None:
        self.assertGreater(len(self.entries), 0)
        found = {e.embranchement for e in self.entries}
        self.assertEqual(found, set(EMBRANCHEMENT_ORDER))

    def test_search_is_accent_and_case_insensitive(self) -> None:
        results = self.catalog.search("murene")
        self.assertTrue(any("Murène" in e.nom_vernaculaire for e in results))

    def test_search_matches_scientific_name(self) -> None:
        results = self.catalog.search("Epinephelus marginatus")
        self.assertTrue(any(e.nom_scientifique == "Epinephelus marginatus" for e in results))

    def test_region_filter_excludes_other_region_only_entries(self) -> None:
        # Catalogue synthetique : independant du contenu reel (qui evolue au
        # fil des mises a jour de la base) pour tester uniquement le
        # mecanisme de filtrage par region.
        atlantic_only = SpeciesEntry("Arthropode", "Espece test Atlantique", "Testus atlanticus", ("atlantique",))
        both_regions = SpeciesEntry("Arthropode", "Espece test partagee", "Testus communis", ("atlantique", "mediterranee"))
        catalog = SpeciesCatalog([atlantic_only, both_regions])

        results_med = catalog.search("Espece test", region="mediterranee")
        self.assertEqual(results_med, [both_regions])
        results_atl = catalog.search("Espece test", region="atlantique")
        self.assertEqual(set(results_atl), {atlantic_only, both_regions})

    def test_empty_query_returns_region_scoped_list(self) -> None:
        all_count = len(self.catalog.search(""))
        med_count = len(self.catalog.search("", region="mediterranee"))
        self.assertLessEqual(med_count, all_count)


if __name__ == "__main__":
    unittest.main()
