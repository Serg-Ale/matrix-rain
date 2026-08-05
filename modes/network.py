"""Network mode — a layered 3D field of nodes, links, and background stars."""

import random

from .base import Mode

# Network motion reads as deliberately slow/cinematic, so it only ever uses
# a fraction of the global speed range: global speed 10 == old global 2.
NETWORK_SPEED_SCALE = 0.2


class NetworkMode(Mode):
    name = 'network'

    def __init__(self):
        self.nodes = []
        self.stars = []
        self.frame = 0
        self.tempo = 1.0

    def reset(self, app):
        """Create a 3D field of nodes and background data points."""
        self.frame = 0
        node_count = max(8, app.density * 2 + 4)
        self.nodes = []
        for _ in range(node_count):
            self.nodes.append([
                random.uniform(-0.85, 0.85),  # x in world space
                random.uniform(-0.85, 0.85),  # y in world space
                random.uniform(0.18, 1.0),    # z: far to near
                random.choice((-1, 1)) * random.uniform(0.12, 0.34),
                random.choice((-1, 1)) * random.uniform(0.08, 0.24),
                random.uniform(0.04, 0.16),
            ])
        self.stars = [
            [random.uniform(-1.0, 1.0), random.uniform(-1.0, 1.0), random.uniform(0.03, 1.0), random.uniform(0.10, 0.32)]
            for _ in range(max(80, app.density * 28))
        ]

    def change_tempo(self, amount: float, app):
        """Set a network-only speed multiplier for deliberately slow scenes."""
        new_tempo = min(1.0, max(0.1, round(self.tempo + amount, 1)))
        if new_tempo == self.tempo:
            return
        self.tempo = new_tempo
        app.show_status('Network tempo: {0:.1f}x'.format(new_tempo))

    def _project(self, app, x: float, y: float, z: float):
        """Project a world-space point with z-depth onto the terminal plane."""
        perspective = 0.35 + z
        screen_x = int((app.width / 2.0) + x * (app.width / 2.0) * perspective)
        screen_y = int((app.height / 2.0) + y * (app.height / 2.0) * perspective)
        return screen_x, screen_y

    def _brightness(self, z: float) -> int:
        """Map depth to the palette: distant dots are dark, near dots glow."""
        return max(1, min(7, 7 - int(z * 5)))

    def _update(self, app):
        """Move 3D nodes and pull the background point cloud toward the viewer."""
        if not self.nodes:
            self.reset(app)

        self.frame += 1
        motion_speed = app.base_speed * NETWORK_SPEED_SCALE * self.tempo

        for node in self.nodes:
            # A small velocity drift avoids predictable billiard-ball paths.
            node[3] = min(0.42, max(-0.42, node[3] + random.uniform(-0.018, 0.018)))
            node[4] = min(0.30, max(-0.30, node[4] + random.uniform(-0.012, 0.012)))
            node[0] += node[3] * motion_speed
            node[1] += node[4] * motion_speed
            node[2] += node[5] * motion_speed
            if abs(node[0]) > 0.95:
                node[3] *= -1
                node[0] = min(0.95, max(-0.95, node[0]))
            if abs(node[1]) > 0.95:
                node[4] *= -1
                node[1] = min(0.95, max(-0.95, node[1]))
            if node[2] > 1.0:
                node[2] = 0.15

        for star in self.stars:
            star[2] += star[3] * motion_speed * 0.35
            if star[2] > 1.0:
                star[0] = random.uniform(-1.0, 1.0)
                star[1] = random.uniform(-1.0, 1.0)
                star[2] = 0.03

    def _draw_line(self, app, start, end, start_z: float, end_z: float, char: str = ':'):
        """Draw a connection with a depth-based color gradient."""
        x0, y0 = start
        x1, y1 = end
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        step_x = 1 if x0 < x1 else -1
        step_y = 1 if y0 < y1 else -1
        error = dx + dy
        steps = max(1, dx + abs(dy))
        step = 0
        while True:
            depth = start_z + (end_z - start_z) * (step / float(steps))
            app.add_char(y0, x0, char, app.get_color(self._brightness(depth), x0))
            if x0 == x1 and y0 == y1:
                break
            twice_error = 2 * error
            if twice_error >= dy:
                error += dy
                x0 += step_x
            if twice_error <= dx:
                error += dx
                y0 += step_y
            step += 1

    def _draw_branch(self, app, start, end, start_z: float, end_z: float, index: int):
        """Add a perpendicular branch so connection topology is easier to read."""
        mid_x = (start[0] + end[0]) // 2
        mid_y = (start[1] + end[1]) // 2
        delta_x = end[0] - start[0]
        delta_y = end[1] - start[1]
        length = max(1.0, (delta_x ** 2 + delta_y ** 2) ** 0.5)
        direction = -1 if index % 2 else 1
        branch_length = 2 + (index % 4)
        branch_x = int(mid_x + ((-delta_y / length) * branch_length * direction))
        branch_y = int(mid_y + ((delta_x / length) * branch_length * direction))
        branch_z = min(1.0, ((start_z + end_z) / 2.0) + 0.16)

        self._draw_line(app, (mid_x, mid_y), (branch_x, branch_y), branch_z, branch_z * 0.8, '.')
        app.add_char(mid_y, mid_x, '+', app.get_color(max(1, self._brightness(branch_z) - 2), mid_x))
        app.add_char(branch_y, branch_x, 'o', app.get_color(self._brightness(branch_z), branch_x))

    def _fill_triangle(self, app, first, second, third):
        """Fill a projected network face with a sparse complementary texture."""
        min_x = max(0, min(first[0], second[0], third[0]))
        max_x = min(app.width - 1, max(first[0], second[0], third[0]))
        min_y = max(0, min(first[1], second[1], third[1]))
        max_y = min(app.height - 1, max(first[1], second[1], third[1]))

        def edge_value(point, line_start, line_end) -> int:
            return ((point[0] - line_end[0]) * (line_start[1] - line_end[1]) -
                    (line_start[0] - line_end[0]) * (point[1] - line_end[1]))

        attr = app.get_contrast_color()
        for y in range(min_y, max_y + 1, 2):
            for x in range(min_x, max_x + 1, 2):
                point = (x, y)
                values = (
                    edge_value(point, first, second), edge_value(point, second, third),
                    edge_value(point, third, first)
                )
                if not (min(values) < 0 < max(values)):
                    app.add_char(y, x, '·', attr)

    def render(self, app):
        """Render a layered network with perspective, gradient links, and packets."""
        self._update(app)
        for star in self.stars:
            star_x, star_y = self._project(app, star[0], star[1], star[2])
            char = '*' if star[2] > 0.82 else '+' if star[2] > 0.52 else '.'
            app.add_char(star_y, star_x, char, app.get_color(self._brightness(star[2]), star_x))

        count = len(self.nodes)
        edges = set()
        triangles = set()
        for index, node in enumerate(self.nodes):
            nearest = sorted(
                range(count),
                key=lambda other: (node[0] - self.nodes[other][0]) ** 2 +
                (node[1] - self.nodes[other][1]) ** 2 +
                ((node[2] - self.nodes[other][2]) * 0.55) ** 2
            )[1:3]
            for target_index in nearest:
                edges.add(tuple(sorted((index, target_index))))
            if len(nearest) == 2:
                triangles.add(tuple(sorted((index, nearest[0], nearest[1]))))

        projected_nodes = [self._project(app, node[0], node[1], node[2]) for node in self.nodes]
        for first_index, second_index, third_index in sorted(triangles)[:app.density + 2]:
            self._fill_triangle(
                app, projected_nodes[first_index], projected_nodes[second_index], projected_nodes[third_index]
            )

        for edge_index, (source_index, target_index) in enumerate(sorted(edges)):
            node = self.nodes[source_index]
            target = self.nodes[target_index]
            node_point = projected_nodes[source_index]
            target_point = projected_nodes[target_index]
            self._draw_line(app, node_point, target_point, node[2], target[2], '=')
            self._draw_branch(app, node_point, target_point, node[2], target[2], edge_index)
            if edge_index % 3 == 0:
                self._draw_branch(app, target_point, node_point, target[2], node[2], edge_index + 1)
            packet_progress = (self.frame * app.base_speed * NETWORK_SPEED_SCALE * self.tempo * 0.09 + edge_index / float(len(edges))) % 1.0
            if edge_index % 2:
                packet_progress = 1.0 - packet_progress
            packet_x = int(node_point[0] + (target_point[0] - node_point[0]) * packet_progress)
            packet_y = int(node_point[1] + (target_point[1] - node_point[1]) * packet_progress)
            packet_z = node[2] + (target[2] - node[2]) * packet_progress
            app.add_char(packet_y, packet_x, '*', app.get_color(max(1, self._brightness(packet_z) - 2), packet_x))

        for node in self.nodes:
            node_x, node_y = self._project(app, node[0], node[1], node[2])
            marker = '@' if node[2] > 0.78 else 'O' if node[2] > 0.45 else 'o'
            app.add_char(node_y, node_x, marker, app.get_color(self._brightness(node[2]), node_x))
