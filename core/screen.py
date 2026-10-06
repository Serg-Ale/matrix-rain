"""Raw-ANSI terminal writer.

``curses`` stays responsible for input, resize detection, and entering/
leaving the alternate screen (see core.app.App) — actual drawing bypasses
its color-pair system entirely and writes true-color/256-color ANSI
sequences directly. ``curses``' pair system can't reliably do true 24-bit
color per cell (most terminfo entries cap ``COLORS`` at 256 even when the
terminal itself supports more), so ``Screen`` is the only thing that ever
writes characters to the terminal.

Only App touches this module — mode plugins never do; they go through
App.add_char/App.add_background/App.get_color instead (see modes/base.py).
"""

import sys

from . import color as color_engine

_CSI = '\x1b['
_RESET = _CSI + '0m'
_RESET_BG = _CSI + '49m'


def _move(row: int, col: int) -> str:
    return '{0}{1};{2}H'.format(_CSI, row + 1, col + 1)


class Screen:
    """One frame's worth of cells: fill them, then flush once.

    Two layers per cell: a foreground character (``set_cell``) and a
    background-only fill (``set_bg``) for depth/wash effects that don't
    have a character of their own (e.g. Pulse's gradient wash). A
    foreground character always wins where both are set for the same
    cell — see `flush`.
    """

    def __init__(self, height: int, width: int):
        self.height = height
        self.width = width
        self._cells = self._blank_grid(height, width)
        self._bg = self._blank_grid(height, width)

    @staticmethod
    def _blank_grid(height: int, width: int):
        return [[None] * width for _ in range(height)]

    def resize(self, height: int, width: int):
        self.height = height
        self.width = width
        self._cells = self._blank_grid(height, width)
        self._bg = self._blank_grid(height, width)

    def clear(self):
        """Start a new frame. Every cell not re-set before flush() draws blank."""
        self._cells = self._blank_grid(self.height, self.width)
        self._bg = self._blank_grid(self.height, self.width)

    def set_cell(self, y: int, x: int, char: str, rgb, bold: bool = False, reverse: bool = False):
        """Queue one foreground character cell. Out-of-bounds is a no-op —
        the same safety curses' addstr + try/except curses.error used to
        give every mode."""
        if 0 <= y < self.height and 0 <= x < self.width:
            self._cells[y][x] = (char, rgb, bold, reverse)

    def set_bg(self, y: int, x: int, rgb):
        """Queue a background-only fill for one cell. Only shows through
        where no foreground character is drawn on top this frame."""
        if 0 <= y < self.height and 0 <= x < self.width:
            self._bg[y][x] = rgb

    def flush(self, truecolor: bool):
        """Write the whole frame to the terminal in one shot."""
        out = [_move(0, 0)]
        for y in range(self.height):
            out.append(_move(y, 0))
            # Tracks the background color actually active on the terminal
            # right now (None means "default/reset") — one meaning, kept
            # in sync by every branch below: a character write always
            # resets it (via _RESET_BG), a bg-only run sets it, and a
            # blank cell resets it if something was active.
            active_bg = None
            for x in range(self.width):
                if y == self.height - 1 and x == self.width - 1:
                    # The bottom-right corner: writing here makes most
                    # terminals auto-wrap and try to scroll the whole
                    # screen up a line (there's no "next line" to wrap
                    # into). curses used to dodge this by swallowing the
                    # curses.error it raises on that exact cell — we just
                    # never draw it, same effect.
                    continue

                cell = self._cells[y][x]
                if cell is not None:
                    char, rgb, bold, reverse = cell
                    # Re-anchor the cursor before every character:
                    # full-width Katakana render as 2 terminal cells in
                    # most fonts, and relying on the terminal's auto
                    # cursor-advance after one drifts every following
                    # cell on the row — same lesson from the
                    # background-depth prototype on issue #1.
                    out.append(_move(y, x))
                    # Always reset the background too: a prior bg-only
                    # run on this row would otherwise bleed through
                    # behind this character.
                    prefix = color_engine.ansi_fg(rgb, truecolor) + _RESET_BG
                    if bold:
                        prefix += _CSI + '1m'
                    if reverse:
                        prefix += _CSI + '7m'
                    out.append(prefix)
                    out.append(char)
                    if bold or reverse:
                        # bold/reverse are sticky SGR state — without this,
                        # the first bold or reversed cell in a frame would
                        # bleed bold/reverse into every following cell (no
                        # foreground color choice turns them back off).
                        out.append(_RESET)
                    active_bg = None
                    continue

                bg_rgb = self._bg[y][x]
                if bg_rgb is not None:
                    if bg_rgb != active_bg:
                        out.append(color_engine.ansi_bg(bg_rgb, truecolor))
                        active_bg = bg_rgb
                    out.append(' ')
                    continue

                if active_bg is not None:
                    out.append(_RESET)
                    active_bg = None
                out.append(' ')

        out.append(_RESET)
        sys.stdout.write(''.join(out))
        sys.stdout.flush()
