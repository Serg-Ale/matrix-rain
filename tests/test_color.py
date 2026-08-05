"""Unit tests for core.color — pure functions, no curses/stdout involved.

Run: python3 -m unittest discover -s tests -t .
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import color  # noqa: E402


class SupportsTruecolorTests(unittest.TestCase):
    def test_truecolor_value(self):
        self.assertTrue(color.supports_truecolor({'COLORTERM': 'truecolor'}))

    def test_24bit_value(self):
        self.assertTrue(color.supports_truecolor({'COLORTERM': '24bit'}))

    def test_case_insensitive(self):
        self.assertTrue(color.supports_truecolor({'COLORTERM': 'TrueColor'}))
        self.assertTrue(color.supports_truecolor({'COLORTERM': '24BIT'}))

    def test_missing_colorterm(self):
        self.assertFalse(color.supports_truecolor({}))

    def test_empty_colorterm(self):
        self.assertFalse(color.supports_truecolor({'COLORTERM': ''}))

    def test_unknown_value(self):
        self.assertFalse(color.supports_truecolor({'COLORTERM': 'yes'}))

    def test_whitespace_is_stripped(self):
        self.assertTrue(color.supports_truecolor({'COLORTERM': '  truecolor  '}))

    def test_defaults_to_os_environ(self):
        # Doesn't assert a specific value (depends on the test runner's
        # environment) — just that omitting `env` doesn't blow up and
        # returns a bool.
        self.assertIsInstance(color.supports_truecolor(), bool)


class GradientTests(unittest.TestCase):
    def test_single_stop_returns_that_stop_for_any_t(self):
        self.assertEqual(color.gradient([(1, 2, 3)], 0.5), (1, 2, 3))
        self.assertEqual(color.gradient([(1, 2, 3)], 0.0), (1, 2, 3))

    def test_t_zero_returns_first_stop(self):
        stops = [(255, 255, 255), (0, 0, 0)]
        self.assertEqual(color.gradient(stops, 0.0), (255, 255, 255))

    def test_t_one_returns_last_stop(self):
        stops = [(255, 255, 255), (0, 0, 0)]
        self.assertEqual(color.gradient(stops, 1.0), (0, 0, 0))

    def test_midpoint_interpolates_linearly(self):
        stops = [(0, 0, 0), (100, 100, 100)]
        self.assertEqual(color.gradient(stops, 0.5), (50, 50, 50))

    def test_multi_stop_hits_exact_breakpoints(self):
        stops = [(255, 255, 255), (0, 255, 0), (0, 0, 0)]
        self.assertEqual(color.gradient(stops, 0.0), (255, 255, 255))
        self.assertEqual(color.gradient(stops, 0.5), (0, 255, 0))
        self.assertEqual(color.gradient(stops, 1.0), (0, 0, 0))

    def test_multi_stop_interpolates_within_a_segment(self):
        stops = [(0, 0, 0), (100, 100, 100), (0, 0, 0)]
        # t=0.25 is halfway through the first of two segments.
        self.assertEqual(color.gradient(stops, 0.25), (50, 50, 50))

    def test_clamps_out_of_range_t(self):
        stops = [(0, 0, 0), (100, 100, 100)]
        self.assertEqual(color.gradient(stops, -1.0), (0, 0, 0))
        self.assertEqual(color.gradient(stops, 2.0), (100, 100, 100))

    def test_empty_stops_raises(self):
        with self.assertRaises(ValueError):
            color.gradient([], 0.5)


class Index256ToRgbTests(unittest.TestCase):
    def test_black(self):
        self.assertEqual(color.index256_to_rgb(0), (0, 0, 0))

    def test_bright_white_index_used_as_every_theme_s_head(self):
        self.assertEqual(color.index256_to_rgb(15), (255, 255, 255))

    def test_cube_corner_is_black(self):
        # 16 is the 6x6x6 cube's (0,0,0) corner.
        self.assertEqual(color.index256_to_rgb(16), (0, 0, 0))

    def test_cube_opposite_corner_is_white(self):
        # 231 is the cube's (5,5,5) corner.
        self.assertEqual(color.index256_to_rgb(231), (255, 255, 255))

    def test_grayscale_ramp_bounds(self):
        self.assertEqual(color.index256_to_rgb(232), (8, 8, 8))
        self.assertEqual(color.index256_to_rgb(255), (238, 238, 238))

    def test_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            color.index256_to_rgb(256)
        with self.assertRaises(ValueError):
            color.index256_to_rgb(-1)


class Nearest256Tests(unittest.TestCase):
    def test_pure_white_snaps_to_a_white_index(self):
        index = color.nearest_256((255, 255, 255))
        self.assertEqual(color.index256_to_rgb(index), (255, 255, 255))

    def test_pure_black_snaps_to_a_black_index(self):
        index = color.nearest_256((0, 0, 0))
        self.assertEqual(color.index256_to_rgb(index), (0, 0, 0))

    def test_round_trip_is_stable_for_exact_256_colors(self):
        # Snapping an RGB that's already an exact 256-color value should
        # come back to that same RGB (possibly via a different index —
        # e.g. a cube color that's also reachable via the gray ramp).
        for index in (15, 46, 196, 21, 236, 244, 232):
            rgb = color.index256_to_rgb(index)
            snapped = color.nearest_256(rgb)
            self.assertEqual(color.index256_to_rgb(snapped), rgb)

    def test_is_deterministic(self):
        rgb = (123, 45, 200)
        self.assertEqual(color.nearest_256(rgb), color.nearest_256(rgb))

    def test_near_gray_prefers_the_grayscale_ramp(self):
        # A neutral dark gray is what the ramp exists for — it should win
        # over the coarser cube even though the cube also has grays.
        index = color.nearest_256((50, 50, 50))
        self.assertGreaterEqual(index, 232)


class AnsiFgTests(unittest.TestCase):
    def test_truecolor_sequence(self):
        self.assertEqual(color.ansi_fg((10, 20, 30), True), '\x1b[38;2;10;20;30m')

    def test_fallback_sequence_uses_256_index_form(self):
        result = color.ansi_fg((255, 255, 255), False)
        self.assertTrue(result.startswith('\x1b[38;5;'))
        self.assertTrue(result.endswith('m'))

    def test_fallback_snaps_to_nearest_256(self):
        rgb = (12, 200, 7)
        expected = '\x1b[38;5;{0}m'.format(color.nearest_256(rgb))
        self.assertEqual(color.ansi_fg(rgb, False), expected)


class AnsiBgTests(unittest.TestCase):
    def test_truecolor_sequence(self):
        self.assertEqual(color.ansi_bg((10, 20, 30), True), '\x1b[48;2;10;20;30m')

    def test_fallback_sequence_uses_256_index_form(self):
        result = color.ansi_bg((255, 255, 255), False)
        self.assertTrue(result.startswith('\x1b[48;5;'))
        self.assertTrue(result.endswith('m'))

    def test_fallback_snaps_to_nearest_256(self):
        rgb = (12, 200, 7)
        expected = '\x1b[48;5;{0}m'.format(color.nearest_256(rgb))
        self.assertEqual(color.ansi_bg(rgb, False), expected)


class DimTests(unittest.TestCase):
    def test_scales_down(self):
        self.assertEqual(color.dim((100, 100, 100), 0.5), (50, 50, 50))

    def test_factor_one_is_unchanged(self):
        self.assertEqual(color.dim((10, 20, 30), 1.0), (10, 20, 30))

    def test_negative_factor_clamps_to_zero(self):
        self.assertEqual(color.dim((10, 10, 10), -1.0), (0, 0, 0))

    def test_never_exceeds_255(self):
        self.assertEqual(color.dim((200, 200, 200), 2.0), (255, 255, 255))


if __name__ == '__main__':
    unittest.main()
