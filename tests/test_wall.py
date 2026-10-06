"""Unit tests for core.wall — the video wall's pure logic (layout, frame
codec). No sockets, no curses.

Run: python3 -m unittest discover -s tests -t .
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import wall  # noqa: E402


class LayoutTests(unittest.TestCase):
    def test_tiles_sit_side_by_side_in_arrival_order(self):
        placements, height, width = wall.layout([(80, 24), (40, 30), (60, 10)])

        self.assertEqual(placements, [(0, 0), (80, 0), (120, 0)])
        self.assertEqual((height, width), (30, 180))

    def test_a_single_tile_is_its_own_canvas(self):
        self.assertEqual(wall.layout([(80, 24)]), ([(0, 0)], 24, 80))

    def test_no_tiles_gives_a_one_cell_canvas(self):
        self.assertEqual(wall.layout([]), ([], 1, 1))


class GridLayoutTests(unittest.TestCase):
    def test_rows_stack_top_to_bottom_and_tiles_go_left_to_right_by_column(self):
        sizes = [(120, 20), (60, 20), (60, 24)]
        positions = [(0, 0), (1, 0), (1, 1)]

        placements, height, width = wall.layout(sizes, positions)

        self.assertEqual(placements, [(0, 0), (0, 20), (60, 20)])
        self.assertEqual((height, width), (44, 120))

    def test_column_order_beats_arrival_order_inside_a_row(self):
        placements, _, _ = wall.layout([(50, 10), (30, 10)], [(0, 1), (0, 0)])

        self.assertEqual(placements, [(30, 0), (0, 0)])

    def test_a_row_is_as_tall_as_its_tallest_tile_and_tiles_align_to_the_top(self):
        sizes = [(40, 10), (40, 25), (80, 5)]
        positions = [(0, 0), (0, 1), (1, 0)]

        placements, height, width = wall.layout(sizes, positions)

        self.assertEqual(placements, [(0, 0), (40, 0), (0, 25)])
        self.assertEqual((height, width), (30, 80))

    def test_canvas_is_as_wide_as_the_widest_row(self):
        _, _, width = wall.layout([(100, 10), (30, 10), (30, 10)], [(0, 0), (1, 0), (1, 1)])

        self.assertEqual(width, 100)

    def test_rows_need_not_be_consecutive(self):
        placements, height, _ = wall.layout([(10, 4), (10, 6)], [(5, 0), (2, 0)])

        self.assertEqual(placements, [(0, 6), (0, 0)])
        self.assertEqual(height, 10)

    def test_tiles_without_a_position_queue_up_in_row_zero_in_arrival_order(self):
        placements, _, _ = wall.layout([(10, 5), (20, 5), (30, 5)], [None, None, None])

        self.assertEqual(placements, [(0, 0), (10, 0), (30, 0)])

    def test_resolved_positions_fill_in_the_arrival_queue(self):
        self.assertEqual(wall.resolve_positions([None, (3, 2), None]), [(0, 0), (3, 2), (0, 2)])

    def test_two_tiles_on_the_same_position_keep_arrival_order(self):
        placements, _, _ = wall.layout([(10, 5), (20, 5)], [(0, 0), (0, 0)])

        self.assertEqual(placements, [(0, 0), (10, 0)])


class ParseAtTests(unittest.TestCase):
    def test_parses_row_and_column(self):
        self.assertEqual(wall.parse_at('1,2'), (1, 2))
        self.assertEqual(wall.parse_at(' 0 , 0 '), (0, 0))

    def test_rejects_malformed_or_negative_positions(self):
        for bad in ('', '1', '1,2,3', 'a,b', '-1,0', '0,-1', '1.5,0', '0,1000000'):
            with self.assertRaises(ValueError):
                wall.parse_at(bad)


class CodecTests(unittest.TestCase):
    def roundtrip(self, message):
        decoder = wall.LineDecoder()
        decoded = decoder.feed(wall.encode(message))
        self.assertEqual(len(decoded), 1)
        return decoded[0]

    def test_size_and_key_messages_roundtrip(self):
        self.assertEqual(self.roundtrip(wall.size_message(90, 30)), {'t': 'size', 'w': 90, 'h': 30})
        self.assertEqual(self.roundtrip(wall.key_message(113)), {'t': 'key', 'k': 113})

    def test_size_message_can_carry_a_declared_position(self):
        self.assertEqual(self.roundtrip(wall.size_message(90, 30, (1, 2))),
                         {'t': 'size', 'w': 90, 'h': 30, 'at': [1, 2]})

    def test_decoder_rejects_a_malformed_position(self):
        raw = (b'{"t":"size","w":9,"h":9,"at":[1]}\n' + b'{"t":"size","w":9,"h":9,"at":[-1,0]}\n'
               + b'{"t":"size","w":9,"h":9,"at":"x"}\n')

        self.assertEqual(wall.LineDecoder().feed(raw), [])

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

    def test_decoder_rejects_absurd_tile_sizes(self):
        raw = (wall.encode(wall.size_message(10 ** 9, 10)) + wall.encode(wall.size_message(10, -1))
               + wall.encode(wall.size_message(90, 30)))

        decoded = wall.LineDecoder().feed(raw)

        self.assertEqual(decoded, [{'t': 'size', 'w': 90, 'h': 30}])

    def test_decoder_drops_a_runaway_line_instead_of_growing_forever(self):
        decoder = wall.LineDecoder()

        self.assertEqual(decoder.feed(b'x' * (wall.MAX_LINE_BYTES + 1)), [])

        # The garbage is gone: the next real message still comes through.
        self.assertEqual(decoder.feed(b'\n' + wall.encode(wall.key_message(5))), [{'t': 'key', 'k': 5}])

    def test_frame_cells_raises_on_malformed_cells(self):
        for bad in ([[1, 2]], [[0, 0, 'a', 5, False, False]], 'nope'):
            with self.assertRaises((ValueError, TypeError)):
                wall.frame_cells({'t': 'frame', 'cells': bad, 'bgs': []})


if __name__ == '__main__':
    unittest.main()
