"""Unit tests for core.palette's gradient derivation.

Run: python3 -m unittest discover -s tests -t .
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import palette  # noqa: E402


class ThemeGradientStopsTests(unittest.TestCase):
    def test_every_theme_has_num_shades_stops(self):
        for theme in palette.COLOR_PALETTE:
            stops = palette.theme_gradient_stops(theme)
            self.assertEqual(len(stops), palette.NUM_SHADES)

    def test_every_theme_starts_white(self):
        # Index 0 in COLOR_PALETTE is always the white head (xterm index 15).
        for theme in palette.COLOR_PALETTE:
            stops = palette.theme_gradient_stops(theme)
            self.assertEqual(stops[0], (255, 255, 255))

    def test_unknown_theme_falls_back_to_green(self):
        self.assertEqual(
            palette.theme_gradient_stops('not-a-real-theme'),
            palette.theme_gradient_stops('green'),
        )

    def test_stops_are_rgb_tuples(self):
        for rgb in palette.theme_gradient_stops('green'):
            self.assertEqual(len(rgb), 3)
            for channel in rgb:
                self.assertTrue(0 <= channel <= 255)


class ContrastRgbTests(unittest.TestCase):
    def test_known_theme(self):
        rgb = palette.contrast_rgb('green')
        self.assertEqual(len(rgb), 3)

    def test_unknown_theme_uses_default_index(self):
        from core.color import index256_to_rgb
        self.assertEqual(palette.contrast_rgb('not-a-real-theme'), index256_to_rgb(51))


if __name__ == '__main__':
    unittest.main()
