import unittest

import numpy as np

from aquabioscope.imaging.crop import CropRect, apply_crop


class CropTest(unittest.TestCase):
    def test_crop_uses_fractions_of_image(self) -> None:
        rgb = np.zeros((100, 200, 3), dtype=np.uint8)
        out = apply_crop(rgb, CropRect(0.25, 0.1, 0.5, 0.5))
        self.assertEqual(out.shape, (50, 100, 3))

    def test_full_or_missing_crop_returns_image_unchanged(self) -> None:
        rgb = np.zeros((10, 20, 3), dtype=np.uint8)
        self.assertIs(apply_crop(rgb, None), rgb)
        self.assertIs(apply_crop(rgb, CropRect(0, 0, 1, 1)), rgb)


if __name__ == "__main__":
    unittest.main()
