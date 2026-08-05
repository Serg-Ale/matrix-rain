"""Pulse mode — bright rings expanding through darkness with a trailing fade.

A background "gradient wash" — a radial color fill whose intensity
breathes with the same pulse phase driving the rings — gives the mode a
sense of fundo->frente depth without adding any extra characters.
Validated in the issue #1 background-depth prototype (variant C,
"Gradient wash").
"""

import math

from core import color as color_engine
from core.charset import MATRIX_CHARS

from .base import Mode

_WASH_DIM_FACTOR = 0.5


class PulseMode(Mode):
    name = 'pulse'

    def __init__(self):
        self.phase = 0.0

    def reset(self, app):
        self.phase = 0.0

    def _draw_wash(self, app, center_x, center_y, max_radius):
        """Radial gradient fill, pushed toward the theme's darker end and
        dimmed further so it reads as background. `breath` ties its
        intensity to the same phase driving the rings, rather than to
        raw frame count, per the prototype's brief."""
        breath = self.phase / max_radius
        for y in range(app.height):
            for x in range(app.width):
                dx = (x - center_x) / 2.0
                dy = y - center_y
                distance = math.sqrt(dx * dx + dy * dy) / max_radius
                t = min(1.0, max(0.0, 0.55 + distance * 0.4 - breath * 0.15))
                rgb = app.get_background_rgb(t, x)
                app.add_background(y, x, color_engine.dim(rgb, _WASH_DIM_FACTOR))

    def render(self, app):
        width, height = app.width, app.height
        center_x = width // 2
        center_y = height // 2
        max_radius = math.sqrt((width / 2.0) ** 2 + (height / 2.0) ** 2)
        if max_radius < 4:
            max_radius = 4

        ring_count = 2 + (app.density // 2)

        self.phase = (self.phase + app.base_speed * 0.75) % max_radius

        self._draw_wash(app, center_x, center_y, max_radius)

        # Non-linear spacing: rings bunched near center, wider near edge.
        ring_radii = []
        for i in range(ring_count):
            normalized = ((self.phase + i * (max_radius / ring_count)) % max_radius) / max_radius
            ring_radii.append((normalized ** 2.5) * max_radius)

        for y in range(height):
            for x in range(0, width, 2):
                dx = (x - center_x) / 2.0
                dy = y - center_y
                distance = math.sqrt(dx * dx + dy * dy)

                # Find nearest ring delta.
                nearest_delta = abs(distance - ring_radii[0])
                for ri in range(1, ring_count):
                    d = abs(distance - ring_radii[ri])
                    if d < nearest_delta:
                        nearest_delta = d

                # Sharp white core -> fast fade into black.
                if nearest_delta < 0.25:
                    brightness = 0
                elif nearest_delta < 0.5:
                    brightness = 1
                elif nearest_delta < 0.9:
                    brightness = 2
                elif nearest_delta < 1.4:
                    brightness = 3
                elif nearest_delta < 2.0:
                    brightness = 4
                elif nearest_delta < 2.8:
                    brightness = 5
                elif nearest_delta < 3.8:
                    brightness = 6
                elif nearest_delta < 5.0:
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
