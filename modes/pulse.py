"""Pulse mode — bright rings expanding through darkness with a trailing fade.

The space between rings is left at the terminal's plain black — no
background wash — so the theme color only ever comes from the rings
themselves, never from a fill behind them. An earlier "gradient wash"
background fill (issue #1 prototype, variant C) tinted that space with
theme color; even pushed toward the dark end of the gradient it still
read as the theme washing the whole screen, especially on true-color
terminals, so it was dropped in favor of true black.
"""

import math

from core.charset import MATRIX_CHARS

from .base import Mode


def _radial_distance(x, y, center_x, center_y):
    """Distance from (x, y) to the pulse center, compensated for terminal
    cells being roughly twice as tall as they are wide (so rings read as
    circular instead of oval)."""
    dx = (x - center_x) / 2.0
    dy = y - center_y
    return math.sqrt(dx * dx + dy * dy)


_MIN_THICKNESS = 0.2
_MAX_THICKNESS = 3.0


class PulseMode(Mode):
    name = 'pulse'

    def __init__(self):
        self.phase = 0.0
        self.thickness = 1.0

    def reset(self, app):
        self.phase = 0.0

    def change_thickness(self, amount: float, app):
        """Scale how far a ring's brightness bands reach — thinner values
        pull the fade in tight around the ring core, thicker values spread
        it out. Kept as its own multiplier (not a 1-10 meter) since it
        only means anything while Pulse is active, same reasoning as
        Network's tempo."""
        new_thickness = min(_MAX_THICKNESS, max(_MIN_THICKNESS, round(self.thickness + amount, 1)))
        if new_thickness == self.thickness:
            return
        self.thickness = new_thickness
        app.show_status('Pulse thickness: {0:.1f}x'.format(new_thickness))

    def render(self, app):
        width, height = app.width, app.height
        center_x = width // 2
        center_y = height // 2
        max_radius = math.sqrt((width / 2.0) ** 2 + (height / 2.0) ** 2)
        if max_radius < 4:
            max_radius = 4

        ring_count = 2 + (app.density // 2)

        self.phase = (self.phase + app.base_speed * 0.75) % max_radius

        # Non-linear spacing: rings bunched near center, wider near edge.
        ring_radii = []
        for i in range(ring_count):
            normalized = ((self.phase + i * (max_radius / ring_count)) % max_radius) / max_radius
            ring_radii.append((normalized ** 2.5) * max_radius)

        for y in range(height):
            for x in range(0, width, 2):
                distance = _radial_distance(x, y, center_x, center_y)

                # Find nearest ring delta.
                nearest_delta = abs(distance - ring_radii[0])
                for ri in range(1, ring_count):
                    d = abs(distance - ring_radii[ri])
                    if d < nearest_delta:
                        nearest_delta = d

                # Sharp white core -> fast fade into black. Scaling the
                # delta (rather than the thresholds) keeps the core itself
                # sharp at any thickness — only how far the fade reaches
                # changes.
                scaled_delta = nearest_delta / self.thickness
                if scaled_delta < 0.25:
                    brightness = 0
                elif scaled_delta < 0.5:
                    brightness = 1
                elif scaled_delta < 0.9:
                    brightness = 2
                elif scaled_delta < 1.4:
                    brightness = 3
                elif scaled_delta < 2.0:
                    brightness = 4
                elif scaled_delta < 2.8:
                    brightness = 5
                elif scaled_delta < 3.8:
                    brightness = 6
                elif scaled_delta < 5.0:
                    brightness = 7
                else:
                    continue

                # Character: bright core is a symbol, fading trail is sparse.
                if brightness <= 1:
                    char = '*' if int(distance + y) % 3 else '@'
                elif brightness <= 3:
                    char = '.' if (x + y) % 3 else ':'
                else:
                    char = MATRIX_CHARS[(x * 7 + y * 3) % len(MATRIX_CHARS)]

                attr = app.get_color(brightness, x)
                app.add_char(y, x, char, attr)

        # Faint centre pulse — just a couple of chars.
        app.add_char(center_y, center_x, '#', app.get_color(0, center_x))
