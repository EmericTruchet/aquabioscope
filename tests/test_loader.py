import unittest

import cv2
import numpy as np

from aquabioscope.imaging import loader


def _distort(image: np.ndarray, params: np.ndarray, out_shape: tuple[int, int]) -> np.ndarray:
    """Simule un RAW non corrigé : pour chaque pixel du "RAW", va chercher le
    pixel correspondant de l'image corrigée (modèle inverse approché par
    itération de point fixe)."""
    h, w = out_shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
    d = loader._normalized_coords(np.stack([xs.ravel(), ys.ravel()], axis=1), (h, w))
    u = d.copy()
    for _ in range(20):
        u = u + (d - loader._apply_lens_model(u, params))
    ih, iw = image.shape[:2]
    src = u * (0.5 * np.hypot(iw, ih)) + np.array([iw / 2, ih / 2])
    return cv2.remap(
        image, src[:, 0].reshape(h, w).astype(np.float32), src[:, 1].reshape(h, w).astype(np.float32),
        cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT,
    )


class LensAlignmentTest(unittest.TestCase):
    def test_recovers_barrel_distortion_like_olympus_tg(self) -> None:
        rng = np.random.default_rng(1)
        texture = cv2.GaussianBlur(rng.integers(0, 255, (600, 800, 3)).astype(np.uint8), (0, 0), 1.5)
        texture = cv2.resize(texture, (1600, 1200), interpolation=cv2.INTER_CUBIC)
        true_params = np.array([0.953, 0.047, -0.003, 0.0005, 0.0001])  # mesures sur un TG-6
        raw_like = _distort(texture, true_params, (1500, 2000))

        params = loader._fit_lens_model(texture, raw_like)

        self.assertIsNotNone(params)
        corner = np.array([[0.8, 0.6]])
        error = np.linalg.norm(loader._apply_lens_model(corner, params) - loader._apply_lens_model(corner, true_params))
        self.assertLess(error, 0.002)

    def test_alignment_gives_up_on_featureless_images(self) -> None:
        flat = np.full((600, 800, 3), (20, 60, 140), dtype=np.uint8)  # eau bleue sans relief
        self.assertIsNone(loader._fit_lens_model(flat, flat))


if __name__ == "__main__":
    unittest.main()
