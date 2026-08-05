"""Rain mode — the original Matrix digital rain effect.

Column-based rendering: two persistent grids (character, brightness) are
updated as columns fall, then drawn in bulk each frame. No horizontal
flickering, long-persistence trails.
"""

import curses
import random
from dataclasses import dataclass

from core.charset import MATRIX_CHARS
from core.palette import NUM_SHADES

from .base import Mode


@dataclass
class Column:
    """Represents a single column of falling rain."""
    x: int                          # Column position
    head_y: float = -1.0            # Current head position (float for smooth movement)
    speed: float = 0.5              # Fall speed (cells per frame)
    trail_length: int = 20          # Length of the visible trail
    spawn_delay: int = 0            # Frames to wait before starting
    active: bool = True             # Whether this column is active
    last_head_y: int = -1           # Last integer head position (for detecting movement)


class RainMode(Mode):
    name = 'rain'

    def __init__(self):
        self.columns = []
        # Character grid: last persistent character at each position.
        self.char_grid = []
        # Brightness grid: 0=brightest, 7=dimmest, 8+=invisible.
        self.brightness_grid = []

    def reset(self, app):
        """(Re)build the grids and columns, sized to the current terminal."""
        self.char_grid = [[' ' for _ in range(app.width)] for _ in range(app.height)]
        self.brightness_grid = [[NUM_SHADES + 1 for _ in range(app.width)] for _ in range(app.height)]

        self.columns = []
        for x in range(app.width - 1):  # -1 to avoid edge issues with wide chars
            col = Column(
                x=x,
                head_y=-random.randint(1, app.height // 2),  # Start above screen
                speed=self._random_speed(app),
                trail_length=self._random_trail_length(app),
                spawn_delay=random.randint(0, 10),  # Short initial delays for quick start
            )
            self.columns.append(col)

        self.apply_density(app)

    def _clear_column(self, x: int):
        """Remove an inactive stream and its persisted trail."""
        for y in range(len(self.char_grid)):
            self.char_grid[y][x] = ' '
            self.brightness_grid[y][x] = NUM_SHADES + 1

    def apply_density(self, app):
        """Apply density immediately by selecting the active streams."""
        if not self.columns:
            return

        active_count = max(1, int(round(len(self.columns) * app.density / 10.0)))
        active_indexes = set(random.sample(range(len(self.columns)), active_count))
        for index, col in enumerate(self.columns):
            active = index in active_indexes
            if col.active and not active:
                self._clear_column(col.x)
            elif not col.active and active:
                col.head_y = -random.randint(1, max(2, app.height // 2))
                col.last_head_y = -1
                col.spawn_delay = random.randint(0, 10)
            col.active = active

    def active_count(self) -> int:
        return sum(col.active for col in self.columns)

    def rescale_speed(self, multiplier: float):
        for col in self.columns:
            col.speed *= multiplier

    def _random_speed(self, app) -> float:
        """Generate a random speed based on base speed setting."""
        # Speed varies between 0.2x and 2.0x of base speed for more variety
        return app.base_speed * random.uniform(0.2, 2.0)

    def _random_trail_length(self, app) -> int:
        """Generate a random trail length - longer trails for more persistence."""
        # Trail length between 1/3 and 2/3 of screen height
        min_len = max(10, app.height // 3)
        max_len = max(min_len + 10, (app.height * 2) // 3)
        return random.randint(min_len, max_len)

    def _random_char(self) -> str:
        """Get a random Matrix character."""
        return random.choice(MATRIX_CHARS)

    def _update_column(self, app, col: Column):
        """Update a single column's state."""
        if not col.active:
            return

        # Handle spawn delay
        if col.spawn_delay > 0:
            col.spawn_delay -= 1
            return

        # Move the head down
        col.head_y += col.speed

        # Check if head has moved to a new cell
        current_head_y = int(col.head_y)

        if current_head_y != col.last_head_y and current_head_y >= 0:
            # Head moved to a new cell - place a new character
            if current_head_y < app.height:
                self.char_grid[current_head_y][col.x] = self._random_char()
                self.brightness_grid[current_head_y][col.x] = 0  # Brightest (head)

            col.last_head_y = current_head_y

        # Update brightness for the trail (create gradient effect)
        for y in range(app.height):
            if col.x >= app.width:
                continue

            distance_from_head = current_head_y - y

            if distance_from_head < 0:
                # Above the head - not part of trail yet
                continue
            elif distance_from_head == 0:
                # The head itself - brightest white
                self.brightness_grid[y][col.x] = 0
            elif distance_from_head <= 3:
                # Glow effect - very bright (shades 1-2)
                # Extended glow zone for more dramatic effect
                self.brightness_grid[y][col.x] = min(distance_from_head, 2)
            elif distance_from_head < col.trail_length:
                # Main trail - gradient from bright to dim
                # Map distance to brightness levels 3-7
                progress = (distance_from_head - 3) / max(1, (col.trail_length - 3))
                brightness = 3 + int(progress * 4)  # 3 to 7
                self.brightness_grid[y][col.x] = min(brightness, NUM_SHADES - 1)
            else:
                # Beyond trail - start fading
                fade_distance = distance_from_head - col.trail_length
                # Slower fade for longer persistence
                fade_brightness = NUM_SHADES + (fade_distance // 2)
                self.brightness_grid[y][col.x] = min(fade_brightness, NUM_SHADES + 10)

        # Respawn column when it's fully off screen
        if col.head_y - col.trail_length > app.height + 5:
            self._respawn_column(app, col)

    def _respawn_column(self, app, col: Column):
        """Respawn a column at the top with new random properties."""
        # Higher density = shorter delay before respawning
        # At density 10, almost immediate respawn
        # At density 1, longer delays
        max_delay = max(1, 20 - (app.density * 2))

        # Random chance to respawn immediately for more organic feel
        if random.random() < (app.density / 10.0):
            col.spawn_delay = random.randint(0, max_delay // 2)
        else:
            col.spawn_delay = random.randint(0, max_delay)

        # Start position - some variation
        col.head_y = -random.randint(1, 8)
        col.last_head_y = -1
        col.speed = self._random_speed(app)
        col.trail_length = self._random_trail_length(app)

    def _draw(self, app):
        """Draw the current state to the screen."""
        for y in range(app.height):  # Draw to all rows including the last
            for x in range(app.width):  # Draw to all columns including the last
                brightness = self.brightness_grid[y][x]

                if brightness > NUM_SHADES:
                    # Invisible - skip drawing (leave as background)
                    continue

                char = self.char_grid[y][x]
                if char == ' ':
                    continue

                try:
                    attr = app.get_color_attr(brightness, x)
                    app.stdscr.addstr(y, x, char, attr)
                except curses.error:
                    # Ignore errors at screen boundaries
                    pass

    def render(self, app):
        for col in self.columns:
            self._update_column(app, col)
        self._draw(app)

    def handle_resize(self, app, old_height: int, old_width: int):
        """Resize grids and columns to the app's current dimensions."""
        new_height, new_width = app.height, app.width

        # Expand or shrink height
        if new_height > old_height:
            for _ in range(new_height - old_height):
                self.char_grid.append([' ' for _ in range(new_width)])
                self.brightness_grid.append([NUM_SHADES + 1 for _ in range(new_width)])
        elif new_height < old_height:
            self.char_grid = self.char_grid[:new_height]
            self.brightness_grid = self.brightness_grid[:new_height]

        # Expand or shrink width
        for y in range(len(self.char_grid)):
            if new_width > len(self.char_grid[y]):
                self.char_grid[y].extend([' ' for _ in range(new_width - len(self.char_grid[y]))])
                self.brightness_grid[y].extend([NUM_SHADES + 1 for _ in range(new_width - len(self.brightness_grid[y]))])
            elif new_width < len(self.char_grid[y]):
                self.char_grid[y] = self.char_grid[y][:new_width]
                self.brightness_grid[y] = self.brightness_grid[y][:new_width]

        # Add or remove columns
        if new_width > old_width:
            for x in range(old_width - 1, new_width - 1):
                col = Column(
                    x=x,
                    head_y=-random.randint(1, app.height // 2),
                    speed=self._random_speed(app),
                    trail_length=self._random_trail_length(app),
                    spawn_delay=random.randint(0, 10),
                )
                self.columns.append(col)
        elif new_width < old_width:
            self.columns = [c for c in self.columns if c.x < new_width - 1]

        self.apply_density(app)
