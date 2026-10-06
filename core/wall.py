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
MAX_GAP = 40                # columns/rows hidden at a seam, at most


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
    0, in arrival order, each taking the first column nobody else holds."""
    taken = {p for p in positions if p is not None}
    resolved = []
    col = 0
    for position in positions:
        if position is None:
            while (0, col) in taken:
                col += 1
            position = (0, col)
            taken.add(position)
        resolved.append(position)
    return resolved


def adjust_gap(gap, axis, delta):
    """``gap`` is ``(columns, rows)``; ``axis`` is ``'h'`` or ``'v'``. Clamped
    to ``0..MAX_GAP``."""
    columns, rows = gap
    if axis == 'h':
        columns = min(MAX_GAP, max(0, columns + delta))
    else:
        rows = min(MAX_GAP, max(0, rows + delta))
    return columns, rows


_STEPS = {'up': (-1, 0), 'down': (1, 0), 'left': (0, -1), 'right': (0, 1)}


def move_position(positions, index, direction):
    """Move tile ``index`` one grid cell (``'up'``/``'down'``/``'left'``/
    ``'right'``) among ``positions`` (resolved ``(row, col)`` per tile).
    Moving onto an occupied cell swaps the two tiles, so positions never
    overlap; the grid's edges (row/col 0 and MAX_GRID_INDEX) stop the move.
    Returns a new list."""
    row, col = positions[index]
    step_row, step_col = _STEPS[direction]
    target = (row + step_row, col + step_col)
    if not all(0 <= v <= MAX_GRID_INDEX for v in target):
        return list(positions)
    moved = list(positions)
    moved[index] = target
    if target in positions:
        moved[positions.index(target)] = (row, col)
    return moved


def displace(positions, want):
    """A newcomer asks for the grid cell ``want``. If a tile already sits
    there it has to make room: returns ``(index, new_position)`` — the
    first free column to its right in the same row (wrapping to the
    start of the row at the grid's edge) — or ``None`` when
    ``want`` is free. (A newcomer has no previous cell to swap into, so
    the occupant steps aside instead.)"""
    if want not in positions:
        return None
    row, col = want
    taken = set(positions)
    for candidate in list(range(col + 1, MAX_GRID_INDEX + 1)) + list(range(col)):
        if (row, candidate) not in taken:
            return positions.index(want), (row, candidate)
    raise ValueError('row {0} is full'.format(row))


def layout(sizes, positions=None, gap=(0, 0)):
    """Place tiles on the canvas.

    ``sizes`` is a list of ``(width, height)`` in arrival order;
    ``positions`` is a same-length list of ``(row, col)`` or ``None`` (see
    resolve_positions). Rows stack top to bottom; inside a row, tiles go
    left to right by column (ties keep arrival order). A row is as tall as
    its tallest tile and tiles align to the top of their row; the canvas
    is as wide as its widest row. Returns
    ``(placements, canvas_height, canvas_width)`` where ``placements`` is
    a list of ``(x, y)`` offsets in arrival order.

    ``gap`` is ``(columns, rows)`` of canvas hidden at each seam — between
    neighbors in a row, and between rows — to make up for the physical frame
    between windows, so the picture reads as continuous behind it. Nothing
    is added before the first tile or after the last.
    """
    gap_columns, gap_rows = gap
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
            x += width + gap_columns
            row_height = max(row_height, height)
        canvas_width = max(canvas_width, x - gap_columns)
        y += row_height + gap_rows
    return placements, max(y - gap_rows, 1), max(canvas_width, 1)


# --- shared settings ----------------------------------------------------------

# The App settings every tile shares. They're named after App's constructor
# arguments (and the CLI's attributes), so ``App(stdscr, **settings)``
# rebuilds them. The wall adds a ``gap`` of its own (see snapshot_of).
SNAPSHOT_KEYS = ('color', 'mode', 'speed', 'density', 'rainbow')

def snapshot_of(app, gap=(0, 0)):
    """The shared settings (SNAPSHOT_KEYS) read off the app, plus the wall's
    own ``gap``. The host broadcasts it, and a terminal leaving the wall
    keeps the last one it saw."""
    return {
        'color': app.color_name,
        'mode': app.active_mode,
        'speed': int(round(app.base_speed * 10)),
        'density': app.density,
        'rainbow': app.rainbow,
        'gap': tuple(gap),
    }


def app_settings(snapshot):
    """The part of a snapshot that is App constructor arguments."""
    return {key: snapshot[key] for key in SNAPSHOT_KEYS}


# --- wire codec ---------------------------------------------------------------
#
# One JSON object per line. Three message types:
#   size  client -> host   {"t":"size","w":..,"h":..[,"at":[row,col]]}
#   config host -> client  {"t":"config","color":..,"mode":..,"speed":..,"density":..,"rainbow":..,"gap":[cols,rows]}
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
    snapshot = {key: message[key] for key in SNAPSHOT_KEYS}
    snapshot['gap'] = tuple(message['gap'])
    return snapshot


def encode(message):
    return (json.dumps(message, separators=(',', ':'), ensure_ascii=False) + '\n').encode('utf-8')


MAX_TILE_SIZE = 10000       # a client can't make the host build a gigantic canvas
MAX_LINE_BYTES = 1 << 24    # a peer that never sends a newline can't grow the buffer forever


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_valid_gap(value):
    return (isinstance(value, list) and len(value) == 2
            and all(_is_int(v) and 0 <= v <= MAX_GAP for v in value))


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
                and isinstance(message.get('rainbow'), bool)
                and _is_valid_gap(message.get('gap')))
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
