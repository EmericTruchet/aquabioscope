import unittest

from aquabioscope.species import EMBRANCHEMENT_ORDER, SpeciesCatalog, SpeciesEntry, load_species


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

    def test_plural_query_finds_singular_entry_and_vice_versa(self) -> None:
        catalog = SpeciesCatalog([
            SpeciesEntry("Cnidaire", "Anémone encroûtante jaune", "Parazoanthus axinellae", ("mediterranee",)),
        ])
        self.assertEqual(len(catalog.search("anemones encroutantes jaunes")), 1)
        self.assertEqual(len(catalog.search("anemone encroutante jaune")), 1)

    def test_fuzzy_fallback_tolerates_typo_when_no_exact_match(self) -> None:
        catalog = SpeciesCatalog([
            SpeciesEntry("Ver", "Salmacine de Dysteri", "Salmacina dysteri", ("mediterranee",)),
        ])
        results = catalog.search("salmacine")  # faute de frappe plausible sur "Salmacina"
        self.assertEqual(len(results), 1)

    def test_fuzzy_fallback_does_not_trigger_when_exact_match_exists(self) -> None:
        # Le flou ne doit pas polluer une recherche qui a deja une reponse
        # exacte nette (evite le bruit et le cout de calcul inutile).
        catalog = SpeciesCatalog([
            SpeciesEntry("Cnidaire", "Bonellie verte", "Bonellia viridis", ("mediterranee",)),
            SpeciesEntry("Poissons osseux", "Donzelle douce", "Ophidion rochei", ("mediterranee",)),
        ])
        results = catalog.search("bonellie")
        self.assertEqual([e.nom_vernaculaire for e in results], ["Bonellie verte"])

    def test_fuzzy_fallback_on_compound_query_matches_significant_word(self) -> None:
        catalog = SpeciesCatalog([
            SpeciesEntry("Bryozoaire", "Dentelle des grottes", "Reteporella mediterranea", ("mediterranee",)),
        ])
        # "retepolle" est une coquille plausible pour "Reteporella"; le mot
        # invente "cavernicolexx" ne doit pas empecher de retrouver l'entree
        # via l'autre mot significatif de la requete.
        results = catalog.search("retepolle cavernicolexx")
        self.assertIn("Reteporella mediterranea", [e.nom_scientifique for e in results])


if __name__ == "__main__":
    unittest.main()
