import unittest

import numpy as np

from divephoto.imaging.color import (
    PRESETS, CustomPresetParams, apply_custom_preset, gray_world_balance, restore_red_channel,
)


class ColorTest(unittest.TestCase):
    def setUp(self) -> None:
        rng = np.random.default_rng(42)
        # Image bleutee synthetique : rouge quasi nul, bleu dominant.
        h, w = 40, 60
        self.blue_cast = np.stack(
            [
                rng.uniform(0, 0.05, (h, w)),
                rng.uniform(0.2, 0.4, (h, w)),
                rng.uniform(0.5, 0.8, (h, w)),
            ],
            axis=-1,
        ).astype(np.float32)
        self.rgb_uint8 = (rng.uniform(0, 1, (h, w, 3)) * 255).astype(np.uint8)

    def test_restore_red_channel_stays_in_bounds(self) -> None:
        out = restore_red_channel(self.blue_cast, strength=1.3)
        self.assertTrue(np.all(out >= 0.0))
        self.assertTrue(np.all(out <= 1.0))

    def test_restore_red_channel_increases_red_mean(self) -> None:
        out = restore_red_channel(self.blue_cast, strength=1.0)
        self.assertGreater(out[..., 0].mean(), self.blue_cast[..., 0].mean())

    def test_gray_world_balance_moves_means_closer_together(self) -> None:
        out = gray_world_balance(self.blue_cast, strength=1.0, max_gain=1.6)
        means_before = [self.blue_cast[..., c].mean() for c in range(3)]
        means_after = [out[..., c].mean() for c in range(3)]
        self.assertLess(max(means_after) - min(means_after), max(means_before) - min(means_before))

    def test_presets_return_valid_uint8_images(self) -> None:
        for name, fn in PRESETS.items():
            with self.subTest(preset=name):
                out = fn(self.rgb_uint8)
                self.assertEqual(out.shape, self.rgb_uint8.shape)
                self.assertEqual(out.dtype, np.uint8)

    def test_apply_custom_preset_returns_valid_image(self) -> None:
        params = CustomPresetParams(red_strength=1.2, gray_balance=0.6, contrast=2.0, sharpen=0.4, saturation=1.3)
        out = apply_custom_preset(self.rgb_uint8, params)
        self.assertEqual(out.shape, self.rgb_uint8.shape)
        self.assertEqual(out.dtype, np.uint8)

    def test_apply_custom_preset_with_zeroed_options_still_valid(self) -> None:
        params = CustomPresetParams(contrast=0.0, sharpen=0.0)
        out = apply_custom_preset(self.rgb_uint8, params)
        self.assertEqual(out.shape, self.rgb_uint8.shape)


if __name__ == "__main__":
    unittest.main()
