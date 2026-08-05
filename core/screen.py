"""Raw-ANSI terminal writer.

``curses`` stays responsible for input, resize detection, and entering/
leaving the alternate screen (see core.app.App) — actual drawing bypasses
its color-pair system entirely and writes true-color/256-color ANSI
sequences directly. ``curses``' pair system can't reliably do true 24-bit
color per cell (most terminfo entries cap ``COLORS`` at 256 even when the
terminal itself supports more), so ``Screen`` is the only thing that ever
writes characters to the terminal.

Only App touches this module — mode plugins never do; they go through
App.add_char/App.get_color instead (see modes/base.py).
"""

import sys

from . import color as color_engine

_CSI = '\x1b['
_RESET = _CSI + '0m'


def _move(row: int, col: int) -> str:
    return '{0}{1};{2}H'.format(_CSI, row + 1, col + 1)


class Screen:
    """One frame's worth of cells: fill them, then flush once."""

    def __init__(self, height: int, width: int):
        self.height = height
        self.width = width
        self._cells = self._blank_grid(height, width)

    @staticmethod
    def _blank_grid(height: int, width: int):
        return [[None] * width for _ in range(height)]

    def resize(self, height: int, width: int):
        self.height = height
        self.width = width
        self._cells = self._blank_grid(height, width)

    def clear(self):
        """Start a new frame. Every cell not re-set before flush() draws blank."""
        self._cells = self._blank_grid(self.height, self.width)

    def set_cell(self, y: int, x: int, char: str, rgb, bold: bool = False, reverse: bool = False):
        """Queue one foreground character cell. Out-of-bounds is a no-op —
        the same safety curses' addstr + try/except curses.error used to
        give every mode."""
        if 0 <= y < self.height and 0 <= x < self.width:
            self._cells[y][x] = (char, rgb, bold, reverse)

    def flush(self, truecolor: bool):
        """Write the whole frame to the terminal in one shot."""
        out = [_move(0, 0)]
        for y in range(self.height):
            out.append(_move(y, 0))
            last_attr = None
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
                if cell is None:
                    if last_attr is not None:
                        out.append(_RESET)
                        last_attr = None
                    out.append(' ')
                    continue

                char, rgb, bold, reverse = cell
                # Re-anchor the cursor before every character: full-width
                # Katakana render as 2 terminal cells in most fonts, and
                # relying on the terminal's auto cursor-advance after one
                # drifts every following cell on the row — same lesson
                # from the background-depth prototype on issue #1.
                out.append(_move(y, x))
                attr = (rgb, bold, reverse)
                if attr != last_attr:
                    prefix = color_engine.ansi_fg(rgb, truecolor)
                    if bold:
                        prefix += _CSI + '1m'
                    if reverse:
                        prefix += _CSI + '7m'
                    out.append(prefix)
                out.append(char)
                # Position is no longer trustworthy after a glyph that may
                # render double-width — force the next cell to re-anchor
                # and re-emit its color regardless of whether it matches.
                last_attr = None

        out.append(_RESET)
        sys.stdout.write(''.join(out))
        sys.stdout.flush()
