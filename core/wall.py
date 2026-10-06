"""Video wall: pure logic shared by host and clients — layout and the wire
codec. No sockets, no curses (core/wall_io.py owns those), so everything
here is unit-testable.

N terminals are *tiles* of one virtual canvas. The host runs the app on the
whole canvas, slices each frame per tile and ships the cells; clients only
draw what they receive.
"""

import json

from modes import MODE_ORDER

from .palette import COLOR_PALETTE

MAX_GRID_INDEX = 999        # row/col of a tile on the wall's grid


def parse_at(text):
    """``"ROW,COL"`` (the ``--at`` flag) into ``(row, col)``; ValueError if
    it isn't two non-negative integers."""
    parts = text.split(',')
    if len(parts) != 2:
        raise ValueError('expected ROW,COL')
    row, col = int(parts[0]), int(parts[1])
    if not (0 <= row <= MAX_GRID_INDEX and 0 <= col <= MAX_GRID_INDEX):
        raise ValueError('ROW and COL must be between 0 and {0}'.format(MAX_GRID_INDEX))
    return row, col


def resolve_positions(positions):
    """Fill in tiles that didn't declare a position: they queue up in row
    0, one column per arrival-order index."""
    return [p if p is not None else (0, i) for i, p in enumerate(positions)]


def layout(sizes, positions=None):
    """Place tiles on the canvas.

    ``sizes`` is a list of ``(width, height)`` in arrival order;
    ``positions`` is a same-length list of ``(row, col)`` or ``None`` (see
    resolve_positions). Rows stack top to bottom; inside a row, tiles go
    left to right by column (ties keep arrival order). A row is as tall as
    its tallest tile and tiles align to the top of their row; the canvas
    is as wide as its widest row. Returns
    ``(placements, canvas_height, canvas_width)`` where ``placements`` is
    a list of ``(x, y)`` offsets in arrival order.
    """
    positions = resolve_positions(positions if positions is not None else [None] * len(sizes))
    rows = {}
    for index, (row, col) in enumerate(positions):
        rows.setdefault(row, []).append((col, index))

    placements = [None] * len(sizes)
    y = canvas_width = 0
    for row in sorted(rows):
        x = row_height = 0
        for _, index in sorted(rows[row]):
            width, height = sizes[index]
            placements[index] = (x, y)
            x += width
            row_height = max(row_height, height)
        canvas_width = max(canvas_width, x)
        y += row_height
    return placements, max(y, 1), max(canvas_width, 1)


# --- shared settings ----------------------------------------------------------

def snapshot_of(app):
    """The settings every tile shares, as a dict whose keys are App's own
    constructor arguments — so ``App(stdscr, **snapshot)`` rebuilds them.
    The host broadcasts it, and a terminal leaving the wall keeps the last
    one it saw."""
    return {
        'color': app.color_name,
        'mode': app.active_mode,
        'speed': int(round(app.base_speed * 10)),
        'density': app.density,
        'rainbow': app.rainbow,
    }


# --- wire codec ---------------------------------------------------------------
#
# One JSON object per line. Three message types:
#   size  client -> host   {"t":"size","w":..,"h":..[,"at":[row,col]]}
#   config host -> client  {"t":"config","color":..,"mode":..,"speed":..,"density":..,"rainbow":..}
#   key   client -> host   {"t":"key","k":<curses key code>}
#   frame host -> client   {"t":"frame","cells":[[y,x,char,[r,g,b],bold,reverse],..],
#                           "bgs":[[y,x,[r,g,b]],..]}

def size_message(width, height, at=None):
    """``at`` is the tile's declared ``(row, col)``, if it declared one."""
    message = {'t': 'size', 'w': width, 'h': height}
    if at is not None:
        message['at'] = list(at)
    return message


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


def config_message(snapshot):
    message = {'t': 'config'}
    message.update(snapshot)
    return message


def config_snapshot(message):
    """A config message back into a snapshot dict."""
    return {key: message[key] for key in ('color', 'mode', 'speed', 'density', 'rainbow')}


def encode(message):
    return (json.dumps(message, separators=(',', ':'), ensure_ascii=False) + '\n').encode('utf-8')


MAX_TILE_SIZE = 10000       # a client can't make the host build a gigantic canvas
MAX_LINE_BYTES = 1 << 24    # a peer that never sends a newline can't grow the buffer forever


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_valid_at(value):
    if value is None:
        return True
    return (isinstance(value, list) and len(value) == 2
            and all(_is_int(v) and 0 <= v <= MAX_GRID_INDEX for v in value))


def _is_tile_dimension(value):
    return _is_int(value) and 0 <= value <= MAX_TILE_SIZE


def _valid(message):
    if not isinstance(message, dict):
        return False
    kind = message.get('t')
    if kind == 'size':
        return (_is_tile_dimension(message.get('w')) and _is_tile_dimension(message.get('h'))
                and _is_valid_at(message.get('at')))
    if kind == 'key':
        return _is_int(message.get('k'))
    if kind == 'config':
        return (isinstance(message.get('color'), str) and message['color'] in COLOR_PALETTE
                and isinstance(message.get('mode'), str) and message['mode'] in MODE_ORDER
                and _is_int(message.get('speed')) and 1 <= message['speed'] <= 10
                and _is_int(message.get('density')) and 1 <= message['density'] <= 10
                and isinstance(message.get('rainbow'), bool))
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
        if len(self._buffer) > MAX_LINE_BYTES:
            self._buffer = b''
        messages = []
        for line in lines:
            try:
                message = json.loads(line.decode('utf-8'))
            except ValueError:
                continue
            if _valid(message):
                messages.append(message)
        return messages
