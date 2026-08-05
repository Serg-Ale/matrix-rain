"""Orchestration: curses lifecycle, color/drawing helpers shared by every
mode, the main loop, input handling, resize, and the live-control panel.

Mode-specific state and rendering live in ``modes/*.py`` instead — this
class only owns what's genuinely shared across all of them.
"""

import curses
import time

from modes import MODE_CLASSES, MODE_ORDER

from .palette import COLOR_PALETTE, CONTRAST_COLORS, CONTRAST_PAIR, NUM_SHADES, RAINBOW_SEQUENCE


class App:
    """Runs the visualizer: curses setup, mode dispatch, live controls."""

    def __init__(self, stdscr, color: str = 'green', speed: int = 5,
                 density: int = 7, screensaver: bool = False, rainbow: bool = False):
        self.stdscr = stdscr
        self.color_name = color
        self.base_speed = speed / 10.0  # Normalize to 0.1 - 1.0
        self.density = density
        self.screensaver = screensaver
        self.rainbow = rainbow
        self.frame_count = 0
        self.panel_visible = not screensaver
        self.status_message = 'Ready — customize while it runs'
        self.contrast_colors_available = False
        self.active_mode = 'rain'

        # Get terminal dimensions
        self.height, self.width = stdscr.getmaxyx()

        # One instance per registered mode, kept alive for the whole run so
        # switching modes doesn't lose state (e.g. Rain's trails keep
        # falling in the background while you're looking at Network).
        self.modes = {name: cls() for name, cls in MODE_CLASSES.items()}

        # Setup curses
        self._setup_curses()
        self._setup_colors()

        # Rain is the only mode that needs to be ready before the first
        # frame — the others initialize lazily on activation/first update,
        # same as before this module was split out.
        self.modes['rain'].reset(self)

    def _setup_curses(self):
        """Configure curses settings."""
        curses.curs_set(0)          # Hide cursor
        self.stdscr.nodelay(True)   # Non-blocking input
        self.stdscr.timeout(0)      # Don't wait for input
        curses.start_color()
        curses.use_default_colors()

    def _setup_colors(self):
        """Initialize color pairs using the 256-color palette."""
        self.contrast_colors_available = False
        # Get the color palette for the selected theme
        palette = COLOR_PALETTE.get(self.color_name, COLOR_PALETTE['green'])

        # Create color pairs for each brightness level
        # Using pairs 1-8 for the main theme
        for i, color_idx in enumerate(palette):
            try:
                curses.init_pair(i + 1, color_idx, -1)
            except curses.error:
                # Fallback to basic colors if 256-color fails
                self._setup_fallback_colors()
                return

        # Setup rainbow color pairs (pairs 10+)
        # Each rainbow color gets 8 shades
        pair_offset = 10
        for theme_idx, theme_name in enumerate(RAINBOW_SEQUENCE):
            theme_palette = COLOR_PALETTE[theme_name]
            for shade_idx, color_idx in enumerate(theme_palette):
                pair_num = pair_offset + (theme_idx * NUM_SHADES) + shade_idx
                try:
                    curses.init_pair(pair_num, color_idx, -1)
                except curses.error:
                    pass

        try:
            curses.init_pair(CONTRAST_PAIR, CONTRAST_COLORS.get(self.color_name, 51), -1)
            self.contrast_colors_available = True
        except curses.error:
            pass

    def _setup_fallback_colors(self):
        """Fallback color setup for terminals without 256-color support."""
        # Map color names to basic curses colors
        color_map = {
            'green': curses.COLOR_GREEN,
            'red': curses.COLOR_RED,
            'blue': curses.COLOR_BLUE,
            'cyan': curses.COLOR_CYAN,
            'magenta': curses.COLOR_MAGENTA,
            'yellow': curses.COLOR_YELLOW,
            'white': curses.COLOR_WHITE,
        }

        base_color = color_map.get(self.color_name, curses.COLOR_GREEN)

        # Create basic color pairs with attributes to simulate gradient
        curses.init_pair(1, curses.COLOR_WHITE, -1)   # Head (white)
        curses.init_pair(2, base_color, -1)           # Glow 1
        curses.init_pair(3, base_color, -1)           # Glow 2
        curses.init_pair(4, base_color, -1)           # Bright
        curses.init_pair(5, base_color, -1)           # Medium-bright
        curses.init_pair(6, base_color, -1)           # Medium
        curses.init_pair(7, base_color, -1)           # Dim
        curses.init_pair(8, base_color, -1)           # Very dim

    # --- shared drawing helpers, used by every mode --------------------------

    def add_char(self, y: int, x: int, char: str, attr: int = 0):
        """Draw one safe terminal cell. Swallows edge/width curses.error."""
        if 0 <= y < self.height and 0 <= x < self.width:
            try:
                self.stdscr.addstr(y, x, char, attr)
            except curses.error:
                pass

    def get_color_attr(self, brightness: int, column_x: int = 0) -> int:
        """Get the curses color attribute for a given brightness level."""
        if brightness >= NUM_SHADES:
            return 0  # Invisible

        if self.rainbow:
            # Cycle through rainbow colors based on column and frame
            theme_idx = (column_x + self.frame_count // 10) % len(RAINBOW_SEQUENCE)
            pair_num = 10 + (theme_idx * NUM_SHADES) + brightness
            attr = curses.color_pair(pair_num)
            # Add bold for brightest shades
            if brightness <= 1:
                attr |= curses.A_BOLD
            return attr

        # Use the pre-defined color pairs (1-8)
        attr = curses.color_pair(brightness + 1)

        # Add bold for the brightest shades (head and glow)
        if brightness <= 2:
            attr |= curses.A_BOLD

        return attr

    def get_contrast_attr(self) -> int:
        """Return a complementary fill color, or a readable fallback."""
        if self.contrast_colors_available:
            return curses.color_pair(CONTRAST_PAIR) | curses.A_DIM
        return curses.A_REVERSE

    # --- live controls ---------------------------------------------------

    def show_status(self, message: str):
        """Store the latest control action for the persistent panel."""
        self.status_message = message

    def _meter(self, value: int) -> str:
        """Return a compact ten-step meter for the control panel."""
        return '[' + ('#' * value) + ('.' * (10 - value)) + ']'

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
            panel_row(',/. net:{0:.1f}x  M/T/R/P controls'.format(network_tempo) if self.active_mode == 'network' else 'M mode  T theme  R rainbow  P hide'),
            '+' + ('-' * (panel_width - 2)) + '+',
        ]

        try:
            for offset, row in enumerate(rows):
                attr = curses.A_REVERSE if offset in (0, 1, 5, 10) else curses.A_BOLD
                self.stdscr.addstr(y + offset, x, row, attr)
        except curses.error:
            pass

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

    def cycle_theme(self):
        """Cycle normal color themes and leave rainbow mode."""
        themes = list(COLOR_PALETTE.keys())
        self.color_name = themes[(themes.index(self.color_name) + 1) % len(themes)]
        self.rainbow = False
        self._setup_colors()
        self.show_status('Theme: {0}'.format(self.color_name))

    def cycle_mode(self):
        """Switch to the next visualizer mode."""
        index = MODE_ORDER.index(self.active_mode)
        self.active_mode = MODE_ORDER[(index + 1) % len(MODE_ORDER)]
        if self.active_mode == 'network':
            self.modes['network'].reset(self)
        self.show_status('Mode: {0}'.format(self.active_mode.upper()))

    def handle_resize(self):
        """Handle terminal resize."""
        new_height, new_width = self.stdscr.getmaxyx()

        if new_height != self.height or new_width != self.width:
            old_height, old_width = self.height, self.width
            self.height, self.width = new_height, new_width

            # Rain's grids/columns always track terminal size, even while
            # another mode is on screen, so switching back to it is never
            # stale — matches the pre-split behavior.
            self.modes['rain'].handle_resize(self, old_height, old_width)
            if self.active_mode == 'network':
                self.modes['network'].reset(self)
            self.stdscr.clear()

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

                # Clear screen
                self.stdscr.erase()

                # Update and draw the active visualizer.
                self.modes[self.active_mode].render(self)

                self._draw_control_panel()

                # Refresh screen
                self.stdscr.refresh()

                # Frame timing
                frame_time = time.time() - frame_start
                delay = max(0.01, base_delay - frame_time)
                time.sleep(delay)

                self.frame_count += 1

        except KeyboardInterrupt:
            pass
