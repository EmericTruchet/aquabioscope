import json
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from aquabioscope import identify
from aquabioscope.imaging.crop import CropRect
from aquabioscope.species import SpeciesCatalog, SpeciesEntry

MEAN = [0.48145466, 0.4578275, 0.40821073]
STD = [0.26862954, 0.26130258, 0.27577711]


def _entry(name: str, latin: str, regions: tuple[str, ...]) -> SpeciesEntry:
    return SpeciesEntry(embranchement="Poissons osseux", nom_vernaculaire=name, nom_scientifique=latin, regions=regions)


class _FakeSession:
    """Remplace onnxruntime : renvoie une empreinte fixe."""

    def __init__(self, embedding: np.ndarray) -> None:
        self.embedding = embedding
        self.inputs = []

    def run(self, _outputs, feeds):
        self.inputs.append(feeds["image"])
        return [self.embedding[None]]


class PreprocessTest(unittest.TestCase):
    def test_shape_and_normalization(self) -> None:
        rgb = np.full((300, 500, 3), 128, dtype=np.uint8)
        x = identify.preprocess(rgb, 224, MEAN, STD)
        self.assertEqual(x.shape, (1, 3, 224, 224))
        self.assertEqual(x.dtype, np.float32)
        expected = (128 / 255 - np.array(MEAN)) / np.array(STD)
        np.testing.assert_allclose(x[0, :, 100, 100], expected, rtol=1e-5)

    def test_center_crop_keeps_middle(self) -> None:
        # bandes gauche/droite noires, centre blanc : le carre central ne doit voir que du blanc
        rgb = np.zeros((224, 672, 3), dtype=np.uint8)
        rgb[:, 224:448] = 255
        x = identify.preprocess(rgb, 224, [0, 0, 0], [1, 1, 1])
        self.assertGreater(x.min(), 0.99)


class SquareZoneTest(unittest.TestCase):
    def test_elongated_zone_becomes_square(self) -> None:
        rgb = np.zeros((1000, 1500, 3), dtype=np.uint8)
        out = identify.square_zone(rgb, CropRect(0.4, 0.45, 0.2, 0.05))  # 300 x 50 px
        self.assertEqual(out.shape[:2], (300, 300))

    def test_zone_at_edge_stays_inside_photo(self) -> None:
        rgb = np.arange(1000 * 1500 * 3, dtype=np.uint32).reshape(1000, 1500, 3)
        out = identify.square_zone(rgb, CropRect(0.95, 0.0, 0.05, 0.4))  # 75 x 400 px, collee au bord
        self.assertEqual(out.shape[:2], (400, 400))
        np.testing.assert_array_equal(out[0, -1], rgb[0, -1])  # recale contre le bord droit

    def test_zone_larger_than_short_side_is_clamped(self) -> None:
        rgb = np.zeros((600, 1500, 3), dtype=np.uint8)
        out = identify.square_zone(rgb, CropRect(0.0, 0.0, 0.9, 1.0))
        self.assertEqual(out.shape[:2], (600, 600))


class RankTest(unittest.TestCase):
    def test_probabilities_sorted_and_normalized(self) -> None:
        text = np.eye(3, dtype=np.float32)
        ranked = identify.rank(np.array([0.1, 0.9, 0.3], dtype=np.float32), text, logit_scale=100.0, k=3)
        self.assertEqual([i for i, _ in ranked], [1, 2, 0])
        self.assertAlmostEqual(sum(p for _, p in ranked), 1.0, places=5)
        self.assertGreater(ranked[0][1], 0.99)


class SpeciesIdentifierTest(unittest.TestCase):
    def _identifier(self, catalog: SpeciesCatalog, names: list[str], text: np.ndarray, embedding: np.ndarray):
        ident = identify.SpeciesIdentifier(catalog, root=Path("inutilise"))
        ident._config = {"image_size": 32, "mean": MEAN, "std": STD, "logit_scale": 100.0}
        ident._names = names
        ident._name_index = {n: i for i, n in enumerate(names)}
        ident._text = text
        ident._input_name = "image"
        ident._session = _FakeSession(embedding)  # deja "charge" : load() ne fait rien
        return ident

    def test_suggestions_limited_to_region_and_known_names(self) -> None:
        catalog = SpeciesCatalog([
            _entry("Sar commun", "Diplodus sargus", ("mediterranee",)),
            _entry("Poisson tropical", "Abudefduf saxatilis", ("caraibes",)),
            _entry("Ajout manuel", "Nomen novum", ("mediterranee",)),  # absent du modele
            _entry("Saupe", "Sarpa salpa", ("mediterranee",)),
            _entry("Doublon", "Sarpa salpa", ("mediterranee",)),
        ] + [_entry(f"Remplissage {i}", f"Genus sp{i}", ("mediterranee",)) for i in range(10)])
        names = ["Abudefduf saxatilis", "Diplodus sargus", "Sarpa salpa"]
        text = np.eye(3, dtype=np.float32)
        # l'image "ressemble" surtout au poisson tropical, puis au sar
        ident = self._identifier(catalog, names, text, np.array([1.0, 0.5, 0.1], dtype=np.float32))

        suggestions = ident.suggest(np.zeros((40, 60, 3), dtype=np.uint8), region="mediterranee", k=5)
        latins = [s.entry.nom_scientifique for s in suggestions]
        self.assertEqual(latins, ["Diplodus sargus", "Sarpa salpa"])  # tropical exclu, doublon fusionne
        self.assertEqual(ident._session.inputs[0].shape, (1, 3, 32, 32))

    def test_without_region_all_species_are_candidates(self) -> None:
        catalog = SpeciesCatalog([
            _entry("Sar commun", "Diplodus sargus", ("mediterranee",)),
            _entry("Poisson tropical", "Abudefduf saxatilis", ("caraibes",)),
        ])
        names = ["Abudefduf saxatilis", "Diplodus sargus"]
        ident = self._identifier(catalog, names, np.eye(2, dtype=np.float32), np.array([1.0, 0.2], dtype=np.float32))
        suggestions = ident.suggest(np.zeros((40, 40, 3), dtype=np.uint8), region=None)
        self.assertEqual(suggestions[0].entry.nom_scientifique, "Abudefduf saxatilis")


class EmbeddingsCheckTest(unittest.TestCase):
    def test_embeddings_for_another_model_are_refused(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            directory = identify.model_dir(tmp)
            directory.mkdir(parents=True)
            (directory / "modele.json").write_text(json.dumps({"nom": identify.MODEL_NAME}), encoding="utf-8")
            embeddings = tmp / "especes_ia.npz"
            np.savez(embeddings, modele=np.array("autre-modele"), noms=np.array(["Diplodus sargus"]),
                     empreintes=np.ones((1, 4), dtype=np.float16))
            ident = identify.SpeciesIdentifier(SpeciesCatalog([]), root=tmp, embeddings_path=embeddings)
            with self.assertRaises(RuntimeError):
                ident.load()

    def test_shipped_embeddings_match_model_and_catalog(self) -> None:
        with np.load(identify.default_embeddings_path()) as data:
            self.assertEqual(str(data["modele"]), identify.MODEL_NAME)
            names = {str(n) for n in data["noms"]}
        binomials = {e.nom_scientifique.strip() for e in SpeciesCatalog().entries
                     if len(e.nom_scientifique.split()) >= 2}
        # une espece ajoutee a la base sans regenerer les empreintes ne serait jamais suggeree
        self.assertEqual(binomials - names, set())


class DownloadTest(unittest.TestCase):
    def _archive(self, folder: Path, files: tuple[str, ...] = identify.MODEL_FILES) -> str:
        archive = folder / "modele.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for name in files:
                zf.writestr(name, json.dumps({"fichier": name}))
        return archive.as_uri()

    def test_download_installs_model(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = tmp / "modeles"
            self.assertFalse(identify.is_installed(root))
            received = []
            identify.download_model(progress=lambda r, t: received.append(r), root=root, url=self._archive(tmp))
            self.assertTrue(identify.is_installed(root))
            self.assertTrue(received)
            # pas de dossier temporaire laisse derriere
            self.assertEqual([p.name for p in root.iterdir()], [identify.MODEL_NAME])

    def test_incomplete_archive_installs_nothing(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = tmp / "modeles"
            with self.assertRaises(OSError):
                identify.download_model(root=root, url=self._archive(tmp, files=("visual.onnx",)))
            self.assertFalse(identify.is_installed(root))

    def test_cancel_installs_nothing(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = tmp / "modeles"
            with self.assertRaises(OSError):
                identify.download_model(cancelled=lambda: True, root=root, url=self._archive(tmp))
            self.assertFalse(identify.is_installed(root))

    def test_new_model_replaces_model_of_previous_version(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = tmp / "modeles"
            (root / "bioclip-ancien-int8").mkdir(parents=True)
            self.assertEqual([p.name for p in identify.old_models(root)], ["bioclip-ancien-int8"])
            identify.download_model(root=root, url=self._archive(tmp))
            self.assertEqual(identify.old_models(root), [])
            self.assertTrue(identify.is_installed(root))

    def test_reinstall_replaces_previous_model(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = tmp / "modeles"
            identify.download_model(root=root, url=self._archive(tmp))
            (identify.model_dir(root) / "ancien-fichier").write_text("x")
            identify.download_model(root=root, url=self._archive(tmp))
            self.assertFalse((identify.model_dir(root) / "ancien-fichier").exists())


if __name__ == "__main__":
    unittest.main()
