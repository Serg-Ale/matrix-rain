"""Scanner mode — a rotating tactical radar HUD.

Not wired into the mode cycle (see ``modes/__init__.py``) — this mirrors
the state before the modular split, where this code existed in the
monolith but ``VISUALIZER_MODES`` never included ``'scanner'`` and its
state (``scanner_angle``/``scanner_targets``/``scanner_structures``) was
never initialized by anything reachable from the run loop. It was already
dead code. Preserved here as-is rather than deleted, since resurrecting or
removing it is a product decision outside this ticket's "no behavior
change" scope.
"""

import math
import random

from .base import Mode


class ScannerMode(Mode):
    name = 'scanner'

    def __init__(self):
        self.targets = []
        self.structures = []
        self.angle = 0.0

    def reset(self, app):
        """Place slowly drifting targets inside the tactical radar field."""
        target_count = max(14, app.density * 5)
        self.targets = []
        while len(self.targets) < target_count:
            x, y = random.uniform(-0.88, 0.88), random.uniform(-0.88, 0.88)
            if (x * x) + (y * y) <= 0.82:
                self.targets.append([
                    x, y, random.uniform(0.03, 0.18),
                    random.choice((-1, 1)) * random.uniform(0.15, 0.45),
                    random.choice((-1, 1)) * random.uniform(0.10, 0.32),
                ])
        ground_y = max(5, app.height - 3)
        layouts = [
            (0.08, 0.18, 'BLD-01'), (0.23, 0.31, 'TWR-02'),
            (0.40, 0.24, 'ARC-03'), (0.58, 0.38, 'TWR-04'),
            (0.76, 0.20, 'BLD-05'), (0.91, 0.29, 'ARC-06'),
        ]
        self.structures = []
        for position, height_ratio, label in layouts:
            building_width = max(4, int(app.width * 0.07))
            building_height = max(3, int(app.height * height_ratio))
            center_x = int(app.width * position)
            roof_y = max(3, ground_y - building_height)
            self.structures.append([center_x, roof_y, label, 0.0, building_width, ground_y])

    def _draw_line(self, app, start, end, brightness: int, char: str = '.'):
        """Draw a radar spoke or beam without coupling it to network state."""
        x0, y0 = start
        x1, y1 = end
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        step_x = 1 if x0 < x1 else -1
        step_y = 1 if y0 < y1 else -1
        error = dx + dy
        while True:
            app.add_char(y0, x0, char, app.get_color(brightness, x0))
            if x0 == x1 and y0 == y1:
                break
            twice_error = 2 * error
            if twice_error >= dy:
                error += dy
                x0 += step_x
            if twice_error <= dx:
                error += dx
                y0 += step_y

    def _draw_text(self, app, y: int, x: int, text: str, brightness: int = 4):
        """Write compact HUD text while keeping edge writes safe."""
        for offset, char in enumerate(text):
            app.add_char(y, x + offset, char, app.get_color(brightness, x + offset))

    def _draw_terrain(self, app):
        """Draw a low-contrast ASCII skyline that creates real scan targets."""
        if not self.structures:
            return

        ground_y = int(self.structures[0][5])
        for x in range(app.width):
            app.add_char(ground_y, x, '_', app.get_color(7, x))
        for structure in self.structures:
            center_x, roof_y = int(structure[0]), int(structure[1])
            building_width, building_ground = int(structure[4]), int(structure[5])
            left = center_x - (building_width // 2)
            right = center_x + (building_width // 2)
            for x in range(left, right + 1):
                app.add_char(roof_y, x, '=', app.get_color(6, x))
            for y in range(roof_y + 1, building_ground):
                for x in range(left, right + 1):
                    if x in (left, right):
                        char, brightness = '|', 6
                    elif (x + y) % 4 == 0:
                        char, brightness = ':', 7
                    else:
                        char, brightness = '#', 7
                    app.add_char(y, x, char, app.get_color(brightness, x))
            # An antenna is a second, smaller structural point above each roof.
            app.add_char(roof_y - 1, center_x, '|', app.get_color(5, center_x))
            app.add_char(roof_y - 2, center_x, '^', app.get_color(6, center_x))

    def render(self, app):
        """Render a rotating tactical radar with target trails and a compact HUD."""
        center_x, center_y = app.width // 2, app.height // 2
        # Use the full terminal as an elliptical scope rather than a small centre widget.
        radius_y = max(3, (app.height // 2) - 1)
        radius_x = max(4, (app.width // 2) - 2)
        self.angle = (self.angle + app.base_speed * 0.12) % (math.pi * 2)

        # Concentric rings make the scanner feel like an instrument, not a grid.
        for ring in (0.25, 0.50, 0.75, 1.0):
            for step in range(0, 144):
                angle = (math.pi * 2 * step) / 144.0
                x = int(center_x + math.cos(angle) * radius_x * ring)
                y = int(center_y + math.sin(angle) * radius_y * ring)
                app.add_char(y, x, '.', app.get_color(7, x))

        self._draw_terrain(app)

        # Radial reference lines and a five-line sweep beam.
        for step in range(8):
            angle = (math.pi * 2 * step) / 8.0
            endpoint = (int(center_x + math.cos(angle) * radius_x), int(center_y + math.sin(angle) * radius_y))
            self._draw_line(app, (center_x, center_y), endpoint, 7)
        for offset, brightness in ((-0.12, 5), (-0.06, 3), (0.0, 1), (0.06, 3), (0.12, 5)):
            angle = self.angle + offset
            endpoint = (int(center_x + math.cos(angle) * radius_x), int(center_y + math.sin(angle) * radius_y))
            self._draw_line(app, (center_x, center_y), endpoint, brightness, '-' if offset == 0.0 else '.')

        locks = 0
        for target in self.targets:
            target[0] += target[3] * app.base_speed * 0.03
            target[1] += target[4] * app.base_speed * 0.03
            radial_distance = (target[0] * target[0]) + (target[1] * target[1])
            if radial_distance > 0.88:
                target[3] *= -1
                target[4] *= -1
                scale = math.sqrt(0.88 / radial_distance)
                target[0] *= scale
                target[1] *= scale

            target_angle = math.atan2(target[1], target[0])
            angle_delta = abs((target_angle - self.angle + math.pi) % (math.pi * 2) - math.pi)
            if angle_delta < 0.10:
                target[2] = 1.0
            else:
                target[2] = max(0.02, target[2] - (0.006 * app.base_speed))

            x = int(center_x + target[0] * radius_x)
            y = int(center_y + target[1] * radius_y)
            energy = target[2]
            if energy > 0.82:
                brightness, marker, locks = 0, '@', locks + 1
            elif energy > 0.58:
                brightness, marker = 2, 'O'
            elif energy > 0.30:
                brightness, marker = 4, 'o'
            elif energy > 0.10:
                brightness, marker = 6, '+'
            else:
                brightness, marker = 7, '.'

            # Motion tail points away from the target and fades into the radar.
            for tail in range(3, 0, -1):
                tail_x = int(x - target[3] * tail * 2)
                tail_y = int(y - target[4] * tail * 2)
                app.add_char(tail_y, tail_x, '.', app.get_color(min(7, brightness + tail), tail_x))
            app.add_char(y, x, marker, app.get_color(brightness, x))

        structure_hits = 0
        for structure in self.structures:
            structure_x, structure_y = int(structure[0]), int(structure[1])
            normalized_x = (structure_x - center_x) / float(max(1, radius_x))
            normalized_y = (structure_y - center_y) / float(max(1, radius_y))
            structure_angle = math.atan2(normalized_y, normalized_x)
            angle_delta = abs((structure_angle - self.angle + math.pi) % (math.pi * 2) - math.pi)
            if angle_delta < 0.075:
                structure[3] = 1.0
            else:
                structure[3] = max(0.02, structure[3] - (0.004 * app.base_speed))

            x, y = structure_x, structure_y
            energy = structure[3]
            if energy > 0.78:
                brightness, marker, structure_hits = 0, '#', structure_hits + 1
            elif energy > 0.38:
                brightness, marker = 2, 'X'
            else:
                brightness, marker = 6, '+'
            app.add_char(y, x, marker, app.get_color(brightness, x))
            if energy > 0.30:
                self._draw_text(app, y - 1, x + 2, str(structure[2]), brightness)

        app.add_char(center_y, center_x, '#', app.get_color(0, center_x))
        if app.height > 4 and app.width > 28:
            self._draw_text(app, 1, 2, 'RADAR // SECTOR 07', 3)
            self._draw_text(app, 2, 2, 'LOCKS:{0:02d}  STRUCT:{1:02d}  SWEEP:{2:03d}'.format(locks, structure_hits, int(math.degrees(self.angle))), 5)
            self._draw_text(app, center_y - radius_y - 1, center_x - 1, 'N', 4)
