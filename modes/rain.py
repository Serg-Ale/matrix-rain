"""Rain mode — the original Matrix digital rain effect.

Column-based rendering: two persistent grids (character, brightness) are
updated as columns fall, then drawn in bulk each frame. No horizontal
flickering, long-persistence trails.

A second, sparser and slower "ghost layer" of columns falls behind the
main trail, giving the mode a sense of fundo->frente depth — the
equivalent of what Network already had via its star field. Validated in
the issue #1 background-depth prototype (variant A, "Ghost layer").
"""

import random
from dataclasses import dataclass

from core import color as color_engine
from core.charset import MATRIX_CHARS
from core.palette import NUM_SHADES

from .base import Mode

# Ghost layer tuning: sparse (most columns have none), much slower than
# even the slowest main-trail column, short trails, and pushed toward the
# theme's darker end + dimmed further so it always reads as "behind".
_GHOST_DENSITY = 0.3
_GHOST_SPEED_RANGE = (0.08, 0.22)
_GHOST_TRAIL_RANGE = (4, 9)
_GHOST_DIM_FACTOR = 0.4


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
        # Ghost (background depth) layer — see module docstring.
        self.ghost_columns = []
        self.ghost_char_cache = {}

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
        self._init_ghost(app)

    def _init_ghost(self, app):
        """(Re)build the sparse background ghost layer, sized to the
        current terminal. Rebuilt wholesale (not incrementally resized)
        on every reset/resize — it's decorative, so simplicity wins over
        preserving exact column state across a resize."""
        self.ghost_columns = []
        self.ghost_char_cache = {}
        for x in range(app.width - 1):
            if random.random() >= _GHOST_DENSITY:
                continue
            self.ghost_columns.append(Column(
                x=x,
                head_y=-random.randint(1, max(2, app.height // 2)),
                speed=self._random_ghost_speed(app),
                trail_length=self._random_ghost_trail(),
                spawn_delay=random.randint(0, 20),
            ))

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

    def _random_ghost_speed(self, app) -> float:
        """Ghost columns fall slower than even the slowest main column —
        that speed gap is what reads as parallax depth, not just a dimmer
        copy of the same rain."""
        return app.base_speed * random.uniform(*_GHOST_SPEED_RANGE)

    def _random_ghost_trail(self) -> int:
        return random.randint(*_GHOST_TRAIL_RANGE)

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

                app.add_char(y, x, char, app.get_color(brightness, x))

    def _update_ghost(self, app):
        for col in self.ghost_columns:
            if col.spawn_delay > 0:
                col.spawn_delay -= 1
                continue
            col.head_y += col.speed
            if col.head_y - col.trail_length > app.height + 5:
                col.head_y = -random.randint(1, 20)
                col.speed = self._random_ghost_speed(app)
                col.trail_length = self._random_ghost_trail()

    def _draw_ghost(self, app):
        """Draw the ghost layer first, so the main trail (drawn right
        after) overwrites it wherever both land on the same cell — that
        draw order is what makes the main rain read as "in front"."""
        for col in self.ghost_columns:
            if col.spawn_delay > 0:
                continue
            head = col.head_y
            trail = col.trail_length
            start_y = max(0, int(head - trail))
            end_y = min(app.height, int(head) + 1)
            for y in range(start_y, end_y):
                distance = head - y
                if distance < 0 or distance > trail:
                    continue
                t = distance / trail if trail else 0.0
                key = (col.x, y)
                char = self.ghost_char_cache.get(key)
                if char is None:
                    char = self._random_char()
                    self.ghost_char_cache[key] = char
                rgb = app.get_background_rgb(min(1.0, 0.5 + t * 0.5), col.x)
                rgb = color_engine.dim(rgb, _GHOST_DIM_FACTOR)
                app.add_char(y, col.x, char, (rgb, False, False))

    def render(self, app):
        self._update_ghost(app)
        self._draw_ghost(app)
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
        self._init_ghost(app)
