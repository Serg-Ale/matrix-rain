"""Koi mode — a pond of koi, lily pads and lotus flowers drawn in matrix glyphs.

Ported from the ``koi-pond`` scene of the Thema ``claude-desktop`` module
(upstream: claude-desktop-themes, MIT). The original paints a pond with a
multi-colour palette; here everything is one theme hue, so the koi patterns
(white body, red patches, black ink spots, gold) are carried by *brightness*
and by *glyph class* (Katakana scales, digits/symbols for red patches).

Everything is a pure function of the mode's clock ``self.t``: the fish follow
closed Lissajous loops, their spine is rebuilt every frame by walking the loop
backwards at equal arc length, and the body is rasterised around that spine.
World units: one row = 1.0, one column = 0.5 (cells are about twice as tall as
wide), so circles stay round.
"""

import math
from functools import lru_cache

from core import color as color_engine
from core.charset import HALF_WIDTH_KATAKANA

from .base import Mode

_KATA = HALF_WIDTH_KATAKANA
_CODE = '0123456789#%&'
_FIN = ':.-~'

# Body half-width per spine index (in units of the fish scale `z`).
_CARP_R = (1.8, 2.8, 3.4, 3.8, 3.9, 3.9, 3.7, 3.4, 3.0, 2.6, 2.2, 1.8, 1.4, 1.1, 0.9, 0.8)
_BODY = len(_CARP_R)
_SPINE_LEN = _BODY + 5

# kind: base colour, fin colour, spots (spine u, lateral v, radius, colour).
_KINDS = (
    {'base': 'w', 'fin': 'f', 'spots': ((2, .6, 1.3, 'r'), (5.5, 1.6, 1.9, 'r'),
                                         (9.5, -1.3, 1.8, 'r'), (13, .8, 1.2, 'r'))},
    {'base': 'w', 'fin': 'f', 'spots': ((1, 0, 1.5, 'r'), (3.5, -1.6, 1.9, 'k'), (6, 1.2, 2.2, 'r'),
                                         (8, 2, 1.6, 'k'), (10, -1, 2, 'r'), (12, -.6, 1.6, 'k'),
                                         (14.5, .4, 1.2, 'k'))},
    {'base': 'g', 'fin': 'F', 'spots': ()},
)

# colour key -> brightness level (0 = brightest, 7 = darkest)
_TONE = {'w': 0, 'r': 2, 'k': 6, 'g': 1, 'l': 0, 'e': 7, 'f': 3, 'F': 3}

# (centre x as fraction of width, centre y as fraction of height, radius, notch angle)
_LILIES = ((.80, .06, 4.2, 2.4), (.95, .14, 6.5, 2.0), (.99, .42, 5.0, 2.8), (.01, .55, 5.5, .2),
           (.20, .97, 4.8, -1.6), (.04, .95, 6.5, -.9), (.97, .95, 5.5, -2.2))
_LOTUS = ((.82, .08, 3.2), (.18, .87, 3.2))


def lilies_for(area):
    """The seven hand-placed pads, plus a few more for big ponds (fixed positions)."""
    extra = min(14, int(area // 900))
    return _LILIES + tuple((.08 + .84 * _unit(k, 11), .06 + .88 * _unit(k, 12), 2.6 + 2.4 * _unit(k, 13),
                            6.28 * _unit(k, 14) - 3.14) for k in range(extra))

_LOOPS = (  # (mx, my, rx, ry, k, dir) for the first three fish; the rest are derived
    (.74, .30, .15, .17, 1, 1),
    (.26, .42, .13, .24, 1, -1),
    (.56, .66, .20, .12, 1, -1),
)


def _h(a, b=0, c=0):
    """Small deterministic integer hash (no ``random``: same input, same frame)."""
    n = (a * 374761393 + b * 668265263 + c * 2147483647 + 1274126177) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n ^ (n >> 16)) & 0xFFFFFFFF


def _unit(a, b=0, c=0):
    return _h(a, b, c) / 4294967296.0


@lru_cache(maxsize=None)
def fish_loop(i):
    """Loop parameters of fish `i`: the original three, then derived ones."""
    if i < len(_LOOPS):
        return _LOOPS[i]
    return (.25 + .5 * _unit(i, 1), .25 + .5 * _unit(i, 2), .10 + .10 * _unit(i, 3),
            .10 + .14 * _unit(i, 4), 1, 1 if _unit(i, 5) < .5 else -1)


_SIZE_MIN, _SIZE_MAX = 0.5, 2.0
_MAX_FISH = 32


def fish_scale(rows, size=1.0):
    """World size of one body segment: smaller on short terminals, times the user's `size`.
    A tiny-font terminal has many rows, so fish stay small and many fit."""
    return max(.18, min(.45, rows / 70.0) * size)


def fish_count(density, width, height, z):
    """Fish in the pond: density sets how much of the water they cover, so smaller
    fish (smaller `z`) means more of them."""
    area = height * (width / 2.0)
    return max(2, min(_MAX_FISH, int(round(area * density * .012 / (170.0 * z * z)))))


def fish_path(cols_w, rows, i, s):
    mx, my, rx, ry, k, direction = fish_loop(i)
    return (cols_w * (mx + rx * math.cos(s * k * direction + i * 2)),
            rows * (my + ry * math.sin(s * direction + i * 2)))


def _path_speed(cols_w, rows, i, s):
    mx, my, rx, ry, k, direction = fish_loop(i)
    vx = cols_w * rx * k * math.sin(s * k * direction + i * 2)
    vy = rows * ry * math.cos(s * direction + i * 2)
    return math.hypot(vx, vy)


def fish_spine(cols_w, rows, i, s, z):
    """`_SPINE_LEN` points spaced `z` apart, head first, walking the loop back from `s`."""
    prev = fish_path(cols_w, rows, i, s)
    pts = [prev]
    need = z
    for _ in range(600):
        if len(pts) >= _SPINE_LEN:
            break
        s -= min(.05, z * .35 / max(_path_speed(cols_w, rows, i, s), 1e-3))
        q = fish_path(cols_w, rows, i, s)
        seg = math.hypot(q[0] - prev[0], q[1] - prev[1])
        while seg >= need and len(pts) < _SPINE_LEN:
            f = need / seg
            prev = (prev[0] + (q[0] - prev[0]) * f, prev[1] + (q[1] - prev[1]) * f)
            pts.append(prev)
            seg = math.hypot(q[0] - prev[0], q[1] - prev[1])
            need = z
        need -= seg
        prev = q
    while len(pts) < _SPINE_LEN:  # degenerate loop: pad with the last point
        pts.append(pts[-1])
    return pts


def _normals(spine):
    out = []
    last = len(spine) - 1
    for k in range(len(spine)):
        ax, ay = spine[max(0, k - 1)]
        bx, by = spine[min(last, k + 1)]
        d = math.hypot(ax - bx, ay - by) or 1.0
        out.append((-(ay - by) / d, (ax - bx) / d))
    return out


def koi_cell(kind, i, spine, norm, u, d, wx, wy, z, t):
    """Classify one cell that is `d` (in units of z) from spine point `u`.

    Returns ``(key, edge, sx, sy)`` — colour key (see `_TONE`), whether it is on the
    dimmer outline, and the body-local coordinates that pin the glyph texture to the
    fish — or None for open water.
    """
    nx, ny = norm[u]
    dx = (wx - spine[u][0]) / z
    dy = (wy - spine[u][1]) / z
    swish = math.sin(t * 3.2 + i * 2) * 1.3 * max(0, u - 9) / 11.0
    v = dx * nx + dy * ny - swish
    av = abs(v)
    sx, sy = u + i * 40, int(round(v * 1.5))
    if u < _BODY and av <= _CARP_R[u] and d <= _CARP_R[u] + 1:
        if 1 <= u <= 2 and abs(av - 1.8) < .55:
            return ('e', False, sx, sy)
        key = kind['base']
        for su, sv, sr, sk in kind['spots']:
            if math.hypot(u - su, v - sv) < sr:
                key = sk
                break
        if kind['base'] == 'g' and av < .9 and u > 1:
            key = 'l'
        return (key, av > _CARP_R[u] - .8, sx, sy)
    fin = kind['fin']
    if u >= _BODY:
        a = u - _BODY + (max(0.0, dy * nx - dx * ny) if u == len(spine) - 1 else 0)
        if av <= .7 + min(a, 4.5) * .5 and a <= 4 + av * .8 and not (a > 4 and av < (a - 4) * 1.4 + .5):
            return (fin, False, sx, sy)
    paddle = 4.8 + .7 * math.sin(t * 2.4 + i)
    if 3 <= u <= 8 and ((u - 5.5) / 2.2) ** 2 + ((av - paddle) / 1.6) ** 2 <= 1:
        return (fin, False, sx, sy)
    if 9 <= u <= 12 and ((u - 10.5) / 1.3) ** 2 + ((av - 3) / 1.1) ** 2 <= 1:
        return (fin, False, sx, sy)
    return None


class KoiMode(Mode):
    name = 'koi'

    def __init__(self):
        self.t = 0.0
        self.size = 1.0
        self._colors = {}

    def change_size(self, amount, app):
        """Scale the fish (and the pond's lilies and ripples with them). Smaller fish
        means more fish for the same density — a pond seen from farther away."""
        new_size = min(_SIZE_MAX, max(_SIZE_MIN, round(self.size + amount, 1)))
        if new_size == self.size:
            return
        self.size = new_size
        app.show_status('Koi size: {0:.1f}x ({1} fish)'.format(
            new_size, fish_count(app.density, app.width, app.height, fish_scale(app.height, new_size))))

    def reset(self, app):
        self._colors.clear()

    # --- colour helpers (cached per theme: gradients are the costly part) ---

    def _fg(self, app, level, x):
        key = (app._resolve_theme(x), level, app.rainbow)
        c = self._colors.get(key)
        if c is None:
            if len(self._colors) > 512:
                self._colors.clear()
            c = self._colors[key] = app.get_color(level, x)
        return c

    def _bg(self, app, tint, x):
        key = (app._resolve_theme(x), 'bg', tint)
        c = self._colors.get(key)
        if c is None:
            c = self._colors[key] = color_engine.dim(app.get_background_rgb(.4, x), tint)
        return c

    def _glyph(self, pool, a, b):
        return pool[(a * 7 + b * 13 + int(self.t * 3)) % len(pool)]

    # --- scene layers ---------------------------------------------------------

    def _draw_water(self, app, scale):
        w, h, t = app.width, app.height, self.t
        # Deep pool: a soft dark wash in the middle of the pond.
        cx, cy, rx, ry = w * .5, h * .45, w * .2, h * .28
        for r in range(max(0, int(cy - ry)), min(h, int(cy + ry) + 1)):
            for c in range(max(0, int(cx - rx)), min(w, int(cx + rx) + 1)):
                e = ((c + .5 - cx) / rx) ** 2 + ((r + .5 - cy) / ry) ** 2
                if e < 1:
                    app.add_background(r, c, self._bg(app, .05 + .10 * (1 - e), c))
        # Ripples: two rings, five centres, each re-seeded every cycle.
        for i in range(5 + min(10, w * h // 1500)):
            phase = t * 1.6 + i * 3.7
            cycle = int(phase // 10)
            rr = phase % 10
            ox = _unit(i, 61, cycle) * w
            oy = _unit(i, 62, cycle) * h
            level = min(7, 4 + int(rr * .35))
            for rad in (rr * scale, (rr - 2.2) * scale):
                if rad < .5:
                    continue
                steps = int(6 * rad) + 8
                for k in range(steps):
                    a = k * 2 * math.pi / steps
                    c = int(round(ox + math.cos(a) * rad * 2))
                    r = int(round(oy + math.sin(a) * rad))
                    if 0 <= r < h and 0 <= c < w:
                        app.add_char(r, c, 'o' if k % 3 else '.', self._fg(app, level, c))
        # Glints: scattered dim glyphs that come and go independently.
        for k in range(int(w * h * .025)):
            epoch = int(t * .4 + k * .137)
            c = _h(k, epoch, 1) % w
            r = _h(k, epoch, 2) % h
            app.add_char(r, c, self._glyph(_KATA, c, r), self._fg(app, 7 if k % 3 else 6, c))

    def _lilies(self, app, sc):
        w, h = app.width, app.height
        cols_w = w * .5
        for fx, fy, rad, notch in lilies_for(h * cols_w):
            rad *= sc
            cx, cy = fx * cols_w, fy * h
            for r in range(max(0, int(cy - rad - 1)), min(h, int(cy + rad + 2))):
                for c in range(max(0, int((cx - rad) * 2) - 1), min(w, int((cx + rad) * 2) + 2)):
                    dx = (c + .5) * .5 - cx
                    dy = r + .5 - cy
                    d = math.hypot(dx, dy)
                    if d > rad:
                        continue
                    th = math.atan2(dy, dx)
                    off = abs(((th - notch) % (2 * math.pi) + 3 * math.pi) % (2 * math.pi) - math.pi)
                    if off < .3 and d > .4:
                        continue
                    app.add_background(r + 1, c + 2, self._bg(app, .06, c))
                    if d > rad - .8:
                        level = 5
                    else:
                        spoke = abs((((th - notch) * 11 / (2 * math.pi)) % 1 + 1) % 1 - .5)
                        level = 4 if d < .8 or (d > 1.2 and spoke > .5 - .35 / d) else 6
                    app.add_char(r, c, self._glyph(_KATA, c, r), self._fg(app, level, c))
        for fx, fy, rad in _LOTUS:
            rad *= sc
            cx, cy = fx * cols_w, fy * h
            for r in range(max(0, int(cy - rad - 1)), min(h, int(cy + rad + 2))):
                for c in range(max(0, int((cx - rad) * 2) - 1), min(w, int((cx + rad) * 2) + 2)):
                    dx = (c + .5) * .5 - cx
                    dy = r + .5 - cy
                    d = math.hypot(dx, dy)
                    th = math.atan2(dy, dx)
                    p = rad * (.55 + .45 * abs(math.cos(4 * th + fx * 9))) * (1 + .07 * math.sin(self.t * .8 + fx * 5))
                    if d < .9:
                        app.add_char(r, c, '*' if (c + r) % 2 else '@', self._fg(app, 0, c))
                    elif d < p * .55:
                        app.add_char(r, c, self._glyph(_KATA, c, r), self._fg(app, 1, c))
                    elif d < p:
                        app.add_char(r, c, self._glyph(_KATA, c, r), self._fg(app, 2, c))

    def _draw_fish(self, app, i, z):
        w, h, t = app.width, app.height, self.t
        cols_w = w * .5
        rate = (.12 + .02 * (i % 4))
        spine = fish_spine(cols_w, h, i, t * rate, z)
        norm = _normals(spine)
        kind = _KINDS[i % len(_KINDS)]
        # Rasterise: every cell near the spine remembers its nearest spine point.
        reach_max = 7 * z
        gx0 = max(0, int((min(p[0] for p in spine) - reach_max) * 2))
        gx1 = min(w - 1, int((max(p[0] for p in spine) + reach_max) * 2) + 1)
        gy0 = max(0, int(min(p[1] for p in spine) - reach_max))
        gy1 = min(h - 1, int(max(p[1] for p in spine) + reach_max) + 1)
        if gx1 < gx0 or gy1 < gy0:
            return
        gw = gx1 - gx0 + 1
        best_d = [1e9] * (gw * (gy1 - gy0 + 1))
        best_u = [-1] * len(best_d)
        for u, (px, py) in enumerate(spine):
            reach = (7 if 3 <= u <= 12 else 5) * z
            c0 = max(gx0, int((px - reach) * 2))
            c1 = min(gx1, int((px + reach) * 2) + 1)
            for r in range(max(gy0, int(py - reach)), min(gy1, int(py + reach) + 1) + 1):
                dy = r + .5 - py
                dy2 = dy * dy
                base = (r - gy0) * gw - gx0
                for c in range(c0, c1 + 1):
                    dx = (c + .5) * .5 - px
                    d2 = dx * dx + dy2
                    k = base + c
                    if d2 < best_d[k]:
                        best_d[k] = d2
                        best_u[k] = u
        cells = []
        for k, u in enumerate(best_u):
            if u < 0:
                continue
            r, c = divmod(k, gw)
            r += gy0
            c += gx0
            res = koi_cell(kind, i, spine, norm, u, math.sqrt(best_d[k]) / z, (c + .5) * .5, r + .5, z, t)
            if res is not None:
                cells.append((r, c, res))
        for r, c, (key, edge, sx, sy) in cells:  # shadow on the pond floor first
            app.add_background(r + 1, c + 2, self._bg(app, .07, c))
        for r, c, (key, edge, sx, sy) in cells:
            level = _TONE[key]
            if edge and key in 'wrkgl':
                level += 1
            if key in 'fF':
                if _h(sx, sy, 5) % 4 == 0:
                    continue
                ch = _FIN[_h(sx, sy, 6) % len(_FIN)]
            elif key == 'e':
                ch = '@'
            elif key == 'r':
                ch = self._glyph(_CODE, sx, sy)
            else:
                ch = self._glyph(_KATA, sx, sy)
            app.add_char(r, c, ch, self._fg(app, min(7, level), c))

    def render(self, app):
        if app.width < 8 or app.height < 4:
            return
        self.t += 0.033 * app.base_speed * 2
        z = fish_scale(app.height, self.size)
        k = max(.3, min(1.0, z * 1.6))   # pond furniture scales with the fish
        self._draw_water(app, k)
        self._lilies(app, k)
        for i in range(fish_count(app.density, app.width, app.height, z)):
            self._draw_fish(app, i, z)
