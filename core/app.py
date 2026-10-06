"""Orchestration: curses lifecycle (input/resize/alt-screen only — see
core/screen.py for why drawing bypasses it), color/drawing helpers shared
by every mode, the main loop, input handling, resize, and the live-control
panel.

Mode-specific state and rendering live in ``modes/*.py`` instead — this
class only owns what's genuinely shared across all of them.
"""

import curses
import time

from modes import MODE_CLASSES, MODE_ORDER

from . import color as color_engine
from .palette import COLOR_PALETTE, NUM_SHADES, RAINBOW_SEQUENCE, contrast_rgb, theme_gradient_stops
from .screen import Screen


class App:
    """Runs the visualizer: curses setup, mode dispatch, live controls."""

    def __init__(self, stdscr, color: str = 'green', mode: str = 'rain', speed: int = 5,
                 density: int = 7, screensaver: bool = False, rainbow: bool = False,
                 canvas_size=None):
        self.stdscr = stdscr
        # Where the drawing area's (height, width) comes from. By default
        # it's the terminal itself; the video wall passes its own callable
        # so the app can draw on a canvas larger than (or unrelated to) the
        # terminal this process happens to be attached to.
        self._canvas_size = canvas_size or stdscr.getmaxyx
        self.color_name = color
        self.base_speed = speed / 10.0  # Normalize to 0.1 - 1.0
        self.density = density
        self.screensaver = screensaver
        self.rainbow = rainbow
        self.frame_count = 0
        self.panel_visible = not screensaver
        self.status_message = 'Ready — customize while it runs'
        # core.cli's argparse choices already guarantee a valid mode for
        # the CLI path — this fallback is for App's own sake as a public
        # constructor (e.g. tests instantiating it directly), not a second
        # enforcement of the same CLI validation.
        self.active_mode = mode if mode in MODE_ORDER else MODE_ORDER[0]

        # Get drawing-area dimensions
        self.height, self.width = self._canvas_size()

        # Detected once — a terminal's true-color support doesn't change
        # mid-session. Everything drawn goes through this same decision, so
        # there's exactly one place (core.color.ansi_fg) that ever branches
        # on it.
        self.truecolor = color_engine.supports_truecolor()
        self.screen = Screen(self.height, self.width)

        # One instance per registered mode, kept alive for the whole run so
        # switching modes doesn't lose state (e.g. Rain's trails keep
        # falling in the background while you're looking at Network).
        self.modes = {name: cls() for name, cls in MODE_CLASSES.items()}

        # Setup curses — input/resize/alt-screen only, no color pairs: see
        # core/screen.py for why drawing bypasses curses entirely.
        self._setup_curses()

        # Rain always needs to be ready before the first frame — its state
        # is tracked continuously regardless of the active mode (see
        # handle_resize/change_density below). Network only resets on
        # activation, same rule whether that happens here at startup or
        # later via cycle_mode.
        self.modes['rain'].reset(self)
        if self.active_mode == 'network':
            self.modes['network'].reset(self)

    def _setup_curses(self):
        """Configure curses settings — input/resize/alt-screen only."""
        curses.curs_set(0)          # Hide cursor
        self.stdscr.nodelay(True)   # Non-blocking input
        self.stdscr.timeout(0)      # Don't wait for input

    # --- shared drawing helpers, used by every mode --------------------------

    def add_char(self, y: int, x: int, char: str, color):
        """Draw one safe terminal cell. `color` is whatever get_color/
        get_contrast_color returned — out-of-bounds and the "invisible"
        sentinel are both silent no-ops, the same safety every mode used
        to get from curses.error."""
        rgb, bold, reverse = color
        if rgb is None:
            return
        self.screen.set_cell(y, x, char, rgb, bold=bold, reverse=reverse)

    def add_background(self, y: int, x: int, rgb):
        """Queue a background-only fill for one cell — for a mode's own
        depth/fill layer (e.g. Pulse's gradient wash) where there's no
        foreground character, just color. A character drawn via add_char
        always wins over this for the same cell."""
        self.screen.set_bg(y, x, rgb)

    def _resolve_theme(self, column_x: int) -> str:
        """Which theme's gradient a cell should draw from — cycling
        through RAINBOW_SEQUENCE by column when rainbow mode is on,
        otherwise the active theme. Shared by get_color and
        get_background_rgb so both branches of "what color is this",
        quantized brightness or continuous t, agree on theme selection.
        """
        if self.rainbow:
            theme_idx = (column_x + self.frame_count // 10) % len(RAINBOW_SEQUENCE)
            return RAINBOW_SEQUENCE[theme_idx]
        return self.color_name

    def get_background_rgb(self, t: float, column_x: int = 0):
        """Continuous-t (0..1) gradient color for a mode's own background
        depth layer — no brightness quantization, no bold/reverse, just
        RGB. Same theme/rainbow selection as get_color, so a background
        layer always matches the active palette. Used by Rain's ghost
        layer and Pulse's gradient wash (see modes/rain.py, modes/pulse.py).
        """
        theme_name = self._resolve_theme(column_x)
        stops = theme_gradient_stops(theme_name)
        return color_engine.gradient(stops, t)

    def get_color(self, brightness: int, column_x: int = 0):
        """Resolve a brightness level (0=brightest, up to NUM_SHADES-1) to
        a (rgb, bold, reverse) color for the current theme/rainbow state.

        Returns (None, False, False) — meaning "don't draw" — for
        brightness at or beyond NUM_SHADES; no mode currently passes one
        that high (each clamps its own trail/fade math beforehand), so
        this is a defensive floor, not a reachable path in practice.
        """
        if brightness >= NUM_SHADES:
            return (None, False, False)

        bold = brightness <= (1 if self.rainbow else 2)
        t = brightness / float(NUM_SHADES - 1)
        rgb = self.get_background_rgb(t, column_x)
        return (rgb, bold, False)

    def get_contrast_color(self):
        """Complementary fill color for the network mode's face texture."""
        rgb = contrast_rgb(self.color_name)
        return (color_engine.dim(rgb, 0.6), False, False)

    # --- live controls ---------------------------------------------------

    def show_status(self, message: str):
        """Store the latest control action for the persistent panel."""
        self.status_message = message

    def _meter(self, value: int) -> str:
        """Return a compact ten-step meter for the control panel."""
        return '[' + ('#' * value) + ('.' * (10 - value)) + ']'

    def _draw_text(self, y: int, x: int, text: str, reverse: bool = False, bold: bool = False):
        """Write a row of panel text — always neutral white, since the
        panel was never theme-colored (it used curses' default terminal
        foreground plus A_REVERSE/A_BOLD before this ticket)."""
        for offset, char in enumerate(text):
            self.add_char(y, x + offset, char, ((255, 255, 255), bold, reverse))

    def _draw_control_panel(self):
        """Draw a compact btop-inspired live-control overlay."""
        panel_width = 43
        panel_height = 11
        if not self.panel_visible or self.height < panel_height + 1 or self.width < panel_width + 1:
            return

        x = self.width - panel_width - 1
        y = self.height - panel_height - 1
        theme = 'RAINBOW' if self.rainbow else self.color_name.upper()

        def panel_row(content: str) -> str:
            return '| ' + content[:39].ljust(39) + ' |'

        network_tempo = self.modes['network'].tempo
        pulse_thickness = self.modes['pulse'].thickness

        if self.active_mode == 'network':
            context_row = ',/. net:{0:.1f}x  M/T/R/P controls'.format(network_tempo)
        elif self.active_mode == 'pulse':
            context_row = ',/. thickness:{0:.1f}x  M/T/R/P controls'.format(pulse_thickness)
        else:
            context_row = 'M mode  T theme  R rainbow  P hide'

        rows = [
            '+' + ('-' * (panel_width - 2)) + '+',
            panel_row('       MATRIX RAIN // LIVE CONTROL'),
            panel_row('Mode: {0:<8} Theme: {1}'.format(self.active_mode.upper(), theme)),
            panel_row('Speed:   {0} {1:>2}/10'.format(self._meter(int(round(self.base_speed * 10))), int(round(self.base_speed * 10)))),
            panel_row('Density: {0} {1:>2}/10'.format(self._meter(self.density), self.density)),
            '+' + ('-' * (panel_width - 2)) + '+',
            panel_row(self.status_message),
            panel_row('W/S or Up/Down : speed'),
            panel_row('A/D or Left/Right : density'),
            panel_row(context_row),
            '+' + ('-' * (panel_width - 2)) + '+',
        ]

        for offset, row in enumerate(rows):
            reverse = offset in (0, 1, 5, 10)
            self._draw_text(y + offset, x, row, reverse=reverse, bold=not reverse)

    def change_speed(self, amount: int):
        """Change speed live and keep every stream's relative variation."""
        old_speed = int(round(self.base_speed * 10))
        new_speed = min(10, max(1, old_speed + amount))
        if new_speed == old_speed:
            return

        multiplier = (new_speed / 10.0) / self.base_speed
        self.base_speed = new_speed / 10.0
        self.modes['rain'].rescale_speed(multiplier)
        self.show_status('Speed: {0}/10'.format(new_speed))

    def change_density(self, amount: int):
        """Change the number of visible streams live."""
        new_density = min(10, max(1, self.density + amount))
        if new_density == self.density:
            return

        self.density = new_density
        # Rain's active-stream set always tracks density, even while another
        # mode is on screen — matches the pre-split behavior.
        self.modes['rain'].apply_density(self)
        if self.active_mode == 'network':
            self.modes['network'].reset(self)
        count = self.modes['rain'].active_count()
        self.show_status('Density: {0}/10 ({1} rain streams)'.format(new_density, count))

    def change_network_tempo(self, amount: float):
        """Set a network-only speed multiplier for deliberately slow scenes."""
        self.modes['network'].change_tempo(amount, self)

    def change_pulse_thickness(self, amount: float):
        """Set a pulse-only ring-thickness multiplier."""
        self.modes['pulse'].change_thickness(amount, self)

    def cycle_theme(self):
        """Cycle normal color themes and leave rainbow mode."""
        themes = list(COLOR_PALETTE.keys())
        self.color_name = themes[(themes.index(self.color_name) + 1) % len(themes)]
        self.rainbow = False
        self.show_status('Theme: {0}'.format(self.color_name))

    def cycle_mode(self):
        """Switch to the next visualizer mode."""
        index = MODE_ORDER.index(self.active_mode)
        self.active_mode = MODE_ORDER[(index + 1) % len(MODE_ORDER)]
        if self.active_mode == 'network':
            self.modes['network'].reset(self)
        self.show_status('Mode: {0}'.format(self.active_mode.upper()))

    def handle_resize(self):
        """Handle a change in the drawing area's size (terminal resize, or
        the wall's canvas growing or shrinking)."""
        new_height, new_width = self._canvas_size()

        if new_height != self.height or new_width != self.width:
            old_height, old_width = self.height, self.width
            self.height, self.width = new_height, new_width
            self.screen.resize(new_height, new_width)

            # Rain's grids/columns always track terminal size, even while
            # another mode is on screen, so switching back to it is never
            # stale — matches the pre-split behavior.
            self.modes['rain'].handle_resize(self, old_height, old_width)
            if self.active_mode == 'network':
                self.modes['network'].reset(self)

    def check_input(self) -> bool:
        """Check for user input. Returns True if should exit."""
        try:
            key = self.stdscr.getch()
            if key != -1:  # A key was pressed
                if self.screensaver:
                    return True  # Exit on any key in screensaver mode
                if key == ord('q') or key == ord('Q') or key == 27:  # q or Escape
                    return True
                elif key in (curses.KEY_UP, ord('+'), ord('='), ord('w'), ord('W')):
                    self.change_speed(1)
                elif key in (curses.KEY_DOWN, ord('-'), ord('_'), ord('s'), ord('S')):
                    self.change_speed(-1)
                elif key in (curses.KEY_RIGHT, ord(']'), ord('d'), ord('D')):
                    self.change_density(1)
                elif key in (curses.KEY_LEFT, ord('['), ord('a'), ord('A')):
                    self.change_density(-1)
                elif key == ord('t') or key == ord('T'):
                    self.cycle_theme()
                elif key == ord('m') or key == ord('M'):
                    self.cycle_mode()
                elif self.active_mode == 'network' and key == ord(','):
                    self.change_network_tempo(-0.1)
                elif self.active_mode == 'network' and key == ord('.'):
                    self.change_network_tempo(0.1)
                elif self.active_mode == 'pulse' and key == ord(','):
                    self.change_pulse_thickness(-0.1)
                elif self.active_mode == 'pulse' and key == ord('.'):
                    self.change_pulse_thickness(0.1)
                elif key == ord('r') or key == ord('R'):
                    self.rainbow = not self.rainbow
                    message = 'Rainbow enabled' if self.rainbow else 'Theme: {0}'.format(self.color_name)
                    self.show_status(message)
                elif key == ord('h') or key == ord('H') or key == ord('?'):
                    self.panel_visible = True
                    self.show_status('Control panel shown')
                elif key == ord('p') or key == ord('P'):
                    self.panel_visible = not self.panel_visible
                    self.show_status('Control panel shown' if self.panel_visible else 'Control panel hidden')
        except curses.error:
            pass
        return False

    def run(self):
        """Main animation loop."""
        # Calculate frame delay based on speed
        # Higher speed = shorter delay = faster animation
        base_delay = 0.03  # 30ms base (~33 FPS)

        try:
            while True:
                frame_start = time.time()

                # Check for input
                if self.check_input():
                    break

                # Handle terminal resize
                self.handle_resize()

                # Start a new frame
                self.screen.clear()

                # Update and draw the active visualizer.
                self.modes[self.active_mode].render(self)

                self._draw_control_panel()

                # Push the frame to the terminal
                self.screen.flush(self.truecolor)

                # Frame timing
                frame_time = time.time() - frame_start
                delay = max(0.01, base_delay - frame_time)
                time.sleep(delay)

                self.frame_count += 1

        except KeyboardInterrupt:
            pass
