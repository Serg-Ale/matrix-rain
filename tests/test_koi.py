"""Unit tests for modes.koi — the pure geometry plus a headless render smoke test.

Run: python3 -m unittest discover -s tests -t .
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.screen import Screen  # noqa: E402
from modes import MODE_CLASSES, MODE_ORDER  # noqa: E402
from modes import koi  # noqa: E402


class FakeApp:
    """Just enough of core.app.App for a mode to draw into a real Screen."""

    def __init__(self, width, height, density=7):
        self.width, self.height = width, height
        self.density = density
        self.base_speed = .5
        self.status = ''
        self.rainbow = False
        self.color_name = 'green'
        self.screen = Screen(height, width)

    def _resolve_theme(self, x):
        return self.color_name

    def get_color(self, level, x=0):
        return ((level * 30, 255 - level * 30, 0), False, False)

    def get_background_rgb(self, t, x=0):
        return (0, int(255 * (1 - t)), 0)

    def show_status(self, message):
        self.status = message

    def add_char(self, y, x, ch, color):
        rgb, bold, reverse = color
        self.screen.set_cell(y, x, ch, rgb, bold=bold, reverse=reverse)

    def add_background(self, y, x, rgb):
        self.screen.set_bg(y, x, rgb)


def frame(width, height, t, density=7, size=1.0):
    app = FakeApp(width, height, density)
    mode = koi.KoiMode()
    mode.t = t
    mode.size = size
    mode.render(app)
    return sorted(app.screen.extract(0, 0, height, width)[0])


class RegistrationTests(unittest.TestCase):
    def test_koi_is_registered_after_the_original_three_modes(self):
        self.assertEqual(MODE_ORDER[:3], ['rain', 'pulse', 'network'])
        self.assertIn('koi', MODE_ORDER)
        self.assertIs(MODE_CLASSES['koi'], koi.KoiMode)


class GeometryTests(unittest.TestCase):
    def test_spine_has_equal_spacing_and_starts_on_the_path(self):
        z = .6
        spine = koi.fish_spine(40, 24, 0, 3.0, z)
        self.assertEqual(len(spine), koi._SPINE_LEN)
        self.assertEqual(spine[0], koi.fish_path(40, 24, 0, 3.0))
        for a, b in zip(spine, spine[1:]):
            self.assertLessEqual(math.hypot(a[0] - b[0], a[1] - b[1]), z + 1e-6)

    def test_every_fish_loop_stays_in_a_sane_part_of_the_pond(self):
        for i in range(8):
            mx, my, rx, ry, _, _ = koi.fish_loop(i)
            self.assertTrue(0 < mx - rx and mx + rx < 1.1 and 0 < my - ry and my + ry < 1)

    def test_smaller_fish_means_more_fish_and_density_adds_fish(self):
        small, big = koi.fish_scale(100, .5), koi.fish_scale(100, 1.5)
        self.assertLess(small, big)
        self.assertGreater(koi.fish_count(7, 200, 100, small), koi.fish_count(7, 200, 100, big))
        self.assertGreater(koi.fish_count(10, 200, 100, big), koi.fish_count(2, 200, 100, big))

    def test_fish_count_stays_within_bounds(self):
        self.assertEqual(koi.fish_count(1, 20, 6, .6), 2)
        self.assertEqual(koi.fish_count(10, 600, 300, .18), 32)


class RenderTests(unittest.TestCase):
    def test_draws_something_at_several_terminal_sizes_without_raising(self):
        for width, height in ((80, 24), (120, 40), (200, 60), (20, 6)):
            for t in (0.0, 3.3, 41.0):
                self.assertTrue(frame(width, height, t), (width, height, t))

    def test_tiny_terminals_are_a_silent_no_op(self):
        self.assertEqual(frame(6, 3, 1.0), [])

    def test_same_clock_gives_the_same_frame(self):
        self.assertEqual(frame(100, 30, 12.5), frame(100, 30, 12.5))

    def test_size_control_clamps_and_reports_the_fish_count(self):
        app = FakeApp(200, 80)
        mode = koi.KoiMode()
        for _ in range(30):
            mode.change_size(-0.1, app)
        self.assertEqual(mode.size, .5)
        self.assertIn('fish', app.status)
        for _ in range(30):
            mode.change_size(0.1, app)
        self.assertEqual(mode.size, 2.0)

    def test_renders_a_big_dense_small_fish_pond(self):
        self.assertTrue(frame(270, 150, 5.0, density=10, size=.5))

    def test_the_pond_moves_as_the_clock_advances(self):
        self.assertNotEqual(frame(100, 30, 12.5), frame(100, 30, 20.0))


if __name__ == '__main__':
    unittest.main()
