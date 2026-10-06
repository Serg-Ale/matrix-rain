"""Unit tests for core.wall — the video wall's pure logic (layout, frame
codec). No sockets, no curses.

Run: python3 -m unittest discover -s tests -t .
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import wall  # noqa: E402
from core.screen import Screen  # noqa: E402


class LayoutTests(unittest.TestCase):
    def test_tiles_sit_side_by_side_in_arrival_order(self):
        placements, height, width = wall.layout([(80, 24), (40, 30), (60, 10)])

        self.assertEqual(placements, [(0, 0), (80, 0), (120, 0)])
        self.assertEqual((height, width), (30, 180))

    def test_a_single_tile_is_its_own_canvas(self):
        self.assertEqual(wall.layout([(80, 24)]), ([(0, 0)], 24, 80))

    def test_no_tiles_gives_a_one_cell_canvas(self):
        self.assertEqual(wall.layout([]), ([], 1, 1))


class CodecTests(unittest.TestCase):
    def roundtrip(self, message):
        decoder = wall.LineDecoder()
        decoded = decoder.feed(wall.encode(message))
        self.assertEqual(len(decoded), 1)
        return decoded[0]

    def test_size_and_key_messages_roundtrip(self):
        self.assertEqual(self.roundtrip(wall.size_message(90, 30)), {'t': 'size', 'w': 90, 'h': 30})
        self.assertEqual(self.roundtrip(wall.key_message(113)), {'t': 'key', 'k': 113})

    def test_frame_roundtrips_with_katakana_and_tuples(self):
        cells = [(0, 1, '\uff71', (0, 255, 70), True, False), (2, 3, '\u30a2', (1, 2, 3), False, True)]
        bgs = [(4, 5, (9, 8, 7))]

        message = self.roundtrip(wall.frame_message(cells, bgs))

        self.assertEqual(wall.frame_cells(message), (cells, bgs))

    def test_each_message_is_one_line(self):
        raw = wall.encode(wall.frame_message([(0, 0, 'a\nb', (1, 1, 1), False, False)], []))

        self.assertEqual(raw.count(b'\n'), 1)
        self.assertTrue(raw.endswith(b'\n'))

    def test_decoder_waits_for_a_complete_line(self):
        raw = wall.encode(wall.frame_message([(0, 0, '\u30a2', (1, 1, 1), False, False)], []))
        decoder = wall.LineDecoder()

        # Split mid-way, inside the 3-byte katakana.
        cut = raw.index('\u30a2'.encode('utf-8')) + 1
        self.assertEqual(decoder.feed(raw[:cut]), [])
        self.assertEqual(len(decoder.feed(raw[cut:])), 1)

    def test_decoder_returns_several_messages_from_one_chunk(self):
        raw = wall.encode(wall.key_message(1)) + wall.encode(wall.key_message(2))

        decoded = wall.LineDecoder().feed(raw)

        self.assertEqual([m['k'] for m in decoded], [1, 2])

    def test_decoder_skips_invalid_lines_and_keeps_going(self):
        raw = (b'not json\n' + b'{"t":"mystery"}\n' + b'[1,2]\n' + b'{"t":"size","w":"x","h":1}\n'
               + wall.encode(wall.key_message(7)))

        decoded = wall.LineDecoder().feed(raw)

        self.assertEqual(decoded, [{'t': 'key', 'k': 7}])


if __name__ == '__main__':
    unittest.main()
