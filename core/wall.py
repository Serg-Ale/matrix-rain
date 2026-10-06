"""Video wall: pure logic shared by host and clients — layout and the wire
codec. No sockets, no curses (core/wall_io.py owns those), so everything
here is unit-testable.

N terminals are *tiles* of one virtual canvas. The host runs the app on the
whole canvas, slices each frame per tile and ships the cells; clients only
draw what they receive.
"""

import json


def layout(sizes):
    """Place tiles side by side, in the order given (arrival order).

    ``sizes`` is a list of ``(width, height)``; returns
    ``(placements, canvas_height, canvas_width)`` where ``placements`` is a
    list of ``(x, y)`` offsets in the same order. The canvas is as tall as
    the tallest tile; tiles align to the top.
    """
    placements = []
    x = 0
    for width, _ in sizes:
        placements.append((x, 0))
        x += width
    canvas_height = max([h for _, h in sizes] + [1])
    return placements, canvas_height, max(x, 1)


# --- wire codec ---------------------------------------------------------------
#
# One JSON object per line. Three message types:
#   size  client -> host   {"t":"size","w":..,"h":..}
#   key   client -> host   {"t":"key","k":<curses key code>}
#   frame host -> client   {"t":"frame","cells":[[y,x,char,[r,g,b],bold,reverse],..],
#                           "bgs":[[y,x,[r,g,b]],..]}

def size_message(width, height):
    return {'t': 'size', 'w': width, 'h': height}


def key_message(key):
    return {'t': 'key', 'k': key}


def frame_message(cells, bgs):
    return {
        't': 'frame',
        'cells': [[y, x, char, list(rgb), bold, reverse] for y, x, char, rgb, bold, reverse in cells],
        'bgs': [[y, x, list(rgb)] for y, x, rgb in bgs],
    }


def frame_cells(message):
    """A frame message back into Screen.load()'s ``(cells, bgs)`` tuples."""
    cells = [(y, x, char, tuple(rgb), bold, reverse) for y, x, char, rgb, bold, reverse in message['cells']]
    bgs = [(y, x, tuple(rgb)) for y, x, rgb in message['bgs']]
    return cells, bgs


def encode(message):
    return (json.dumps(message, separators=(',', ':'), ensure_ascii=False) + '\n').encode('utf-8')


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _valid(message):
    if not isinstance(message, dict):
        return False
    kind = message.get('t')
    if kind == 'size':
        return _is_int(message.get('w')) and _is_int(message.get('h'))
    if kind == 'key':
        return _is_int(message.get('k'))
    if kind == 'frame':
        return isinstance(message.get('cells'), list) and isinstance(message.get('bgs'), list)
    return False


class LineDecoder:
    """Turns a byte stream into messages. Bytes are buffered until a full
    line arrives (a read can end mid-line, even mid-character); lines that
    aren't a valid message are skipped rather than ending the stream."""

    def __init__(self):
        self._buffer = b''

    def feed(self, data):
        self._buffer += data
        *lines, self._buffer = self._buffer.split(b'\n')
        messages = []
        for line in lines:
            try:
                message = json.loads(line.decode('utf-8'))
            except ValueError:
                continue
            if _valid(message):
                messages.append(message)
        return messages
