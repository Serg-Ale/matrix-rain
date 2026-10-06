"""Unit tests for core.screen.Screen's slice/rebuild interface — the seam the
video wall uses to ship one tile's worth of a frame to another terminal.

Run: python3 -m unittest discover -s tests -t .
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.screen import Screen  # noqa: E402

WHITE = (255, 255, 255)
RED = (200, 0, 0)


class ExtractTests(unittest.TestCase):
    def test_extract_returns_cells_inside_the_rectangle_in_local_coordinates(self):
        screen = Screen(10, 20)
        screen.set_cell(3, 5, 'A', WHITE)
        screen.set_cell(4, 6, 'B', RED, bold=True)
        screen.set_cell(0, 0, 'Z', WHITE)  # outside the rectangle

        cells, bgs = screen.extract(3, 5, 2, 3)

        self.assertEqual(sorted(cells), [
            (0, 0, 'A', WHITE, False, False),
            (1, 1, 'B', RED, True, False),
        ])
        self.assertEqual(bgs, [])

    def test_extract_returns_background_fills_only_where_no_character_is_drawn(self):
        screen = Screen(10, 20)
        screen.set_bg(2, 2, RED)
        screen.set_bg(2, 3, RED)
        screen.set_cell(2, 3, 'A', WHITE)  # the character wins over the fill

        cells, bgs = screen.extract(2, 2, 1, 2)

        self.assertEqual(cells, [(0, 1, 'A', WHITE, False, False)])
        self.assertEqual(bgs, [(0, 0, RED)])

    def test_extract_drops_a_full_width_character_on_the_rectangles_last_column(self):
        screen = Screen(10, 20)
        screen.set_cell(1, 4, '\u30a2', WHITE)  # full-width katakana, last column
        screen.set_cell(1, 3, '\u30a4', WHITE)  # full-width katakana, not last
        screen.set_cell(2, 4, 'A', WHITE)        # narrow character, last column

        cells, _ = screen.extract(0, 0, 5, 5)

        self.assertEqual(sorted(c[:3] for c in cells), [(1, 3, '\u30a4'), (2, 4, 'A')])

    def test_extract_keeps_a_half_width_katakana_on_the_last_column(self):
        screen = Screen(10, 20)
        screen.set_cell(1, 4, '\uff71', WHITE)  # half-width katakana

        cells, _ = screen.extract(0, 0, 5, 5)

        self.assertEqual([c[:3] for c in cells], [(1, 4, '\uff71')])


class LoadTests(unittest.TestCase):
    def test_load_rebuilds_an_extracted_rectangle(self):
        source = Screen(10, 20)
        source.set_cell(3, 5, 'A', WHITE)
        source.set_cell(4, 6, 'B', RED, bold=True, reverse=True)
        source.set_bg(4, 5, RED)

        tile = Screen(2, 3)
        tile.load(*source.extract(3, 5, 2, 3))

        self.assertEqual(tile.extract(0, 0, 2, 3), source.extract(3, 5, 2, 3))

    def test_load_replaces_whatever_the_screen_held_before(self):
        screen = Screen(2, 3)
        screen.set_cell(0, 0, 'old', WHITE)
        screen.set_bg(1, 1, RED)

        screen.load([(1, 2, 'N', WHITE, False, False)], [])

        self.assertEqual(screen.extract(0, 0, 2, 3), ([(1, 2, 'N', WHITE, False, False)], []))

    def test_load_ignores_cells_outside_the_screen(self):
        screen = Screen(2, 3)

        screen.load([(5, 5, 'X', WHITE, False, False)], [(9, 9, RED)])

        self.assertEqual(screen.extract(0, 0, 2, 3), ([], []))


if __name__ == '__main__':
    unittest.main()
