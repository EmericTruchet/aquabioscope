import unittest

import numpy as np

import cv2

from aquabioscope.imaging.color import (
    PRESETS, CustomPresetParams, apply_custom_preset, gray_world_balance, preset_naturel,
    preset_profondeur, restore_red_channel, water_cast,
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

    def test_water_cast_distinguishes_flash_from_blue_water(self) -> None:
        self.assertGreater(water_cast(self.blue_cast), 0.8)
        warm = self.blue_cast[..., ::-1].copy()  # rouge dominant, comme au flash
        self.assertEqual(water_cast(warm), 0.0)

    def test_blue_water_presets_do_not_turn_purple(self) -> None:
        # Scene d'eau bleue plausible : canaux correles (meme relief), rouge
        # quasi absorbe - c'est la que les presets v1 viraient au violet.
        rng = np.random.default_rng(0)
        relief = cv2.GaussianBlur(rng.uniform(0.3, 1.0, (60, 80)).astype(np.float32), (0, 0), 3)
        scene = np.stack([0.06 * relief, 0.45 * relief, 0.85 * relief], axis=-1)
        blue_u8 = (np.clip(scene, 0, 1) * 255).astype(np.uint8)

        def hue(rgb_u8: np.ndarray) -> float:
            # angle de teinte LAB (degres) : ~-80 bleu, ~-40 violet, ~0 magenta/rouge
            lab = cv2.cvtColor(rgb_u8.astype(np.float32) / 255, cv2.COLOR_RGB2LAB)
            return float(np.degrees(np.arctan2(np.median(lab[..., 2]), np.median(lab[..., 1]))))

        before = hue(blue_u8)
        for fn in (preset_naturel, preset_profondeur):
            with self.subTest(preset=fn.__name__):
                self.assertLess(hue(fn(blue_u8)), before + 10)  # pas de rotation vers le violet

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
