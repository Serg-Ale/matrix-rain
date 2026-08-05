#!/usr/bin/env python3
"""
PROTOTYPE — throwaway, NOT part of the real codebase.

Question this answers: "what should the background/depth layer of Rain and
Pulse look like?" — left open in spec issue #1 (github.com/Serg-Ale/matrix-rain
issue #1), item 7 ("Out of Scope: design concreto do fundo de Rain/Pulse").

Network already solves "does this mode feel like it has depth" via its own
3D `network_stars` field, coupled to its camera model. This prototype
searches for the Rain/Pulse equivalent — NOT a shared background component,
but the same *family of techniques*, applied so each mode keeps its own
personality (see spec decision 5/6).

Three variants, defined the same way for BOTH modes so you're comparing the
*technique*, not two unrelated ideas:

  A — Ghost layer    : a second, dimmer/slower copy of the mode's own motion,
                        offset in phase (parallax — foreground fast & bright,
                        background slow & dim).
  B — Particle field : an independent field of small elements with their own
                        life cycle, closer in spirit to what Network already
                        does with `network_stars`.
  C — Gradient wash   : no extra elements at all — just a background color
                        gradient driven by state (time / pulse phase). Pure
                        depth-via-color, cheapest to render.

Colors here are PLACEHOLDERS — exact per-mode palette/personality is a
separate decision (spec's decision 5), out of scope for this prototype.
Only the background *mechanism* is being judged.

Rendering technique matches the real target architecture (spec decision 3):
true color via direct ANSI escapes, terminal put in raw mode for input only
— no `curses` color pairs involved. Terminal size is read once at startup;
this prototype does not handle resize (skip polish — see /prototype rules).

Run:
    python3 prototype_depth_bg.py

Keys:
    m           toggle Rain / Pulse
    a / d       cycle background variant A / B / C (also <- / ->, when your
                terminal's escape sequence for arrows gets recognized —
                a/d are the reliable fallback across terminals)
    q, Esc      quit (restores the terminal)

The status bar shows the raw code of the last key read — if arrows still
don't register on your terminal, that value tells us exactly what bytes it
sends so the parser can be adjusted.
"""

import importlib.machinery
import importlib.util
import math
import os
import random
import select
import sys
import termios
import time
import tty

# --- reuse the production charset only (not the rendering code) -----------

_HERE = os.path.dirname(os.path.abspath(__file__))
_loader = importlib.machinery.SourceFileLoader("matrix_rain_prod", os.path.join(_HERE, "matrix-rain"))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
_mr = importlib.util.module_from_spec(_spec)
_loader.exec_module(_mr)
KATAKANA = _mr.HALF_WIDTH_KATAKANA + _mr.FULL_WIDTH_KATAKANA

MODES = ["rain", "pulse"]
VARIANTS = ["A", "B", "C"]
VARIANT_NAMES = {
    "A": "Ghost layer",
    "B": "Particle field",
    "C": "Gradient wash",
}

# --- ANSI helpers -----------------------------------------------------------

CSI = "\x1b["
HIDE_CURSOR = f"{CSI}?25l"
SHOW_CURSOR = f"{CSI}?25h"
ALT_ON = f"{CSI}?1049h"
ALT_OFF = f"{CSI}?1049l"
RESET = f"{CSI}0m"


def move(row, col):
    return f"{CSI}{row + 1};{col + 1}H"


def fg(rgb):
    r, g, b = rgb
    return f"{CSI}38;2;{r};{g};{b}m"


def bg(rgb):
    r, g, b = rgb
    return f"{CSI}48;2;{r};{g};{b}m"


def lerp(a, b, t):
    return a + (b - a) * t


def gradient(stops, t):
    """stops: list of RGB tuples, evenly spaced. t in [0,1]."""
    t = max(0.0, min(1.0, t))
    n = len(stops) - 1
    pos = t * n
    i = min(int(pos), n - 1)
    frac = pos - i
    a, b = stops[i], stops[i + 1]
    return (
        int(lerp(a[0], b[0], frac)),
        int(lerp(a[1], b[1], frac)),
        int(lerp(a[2], b[2], frac)),
    )


def dim(rgb, factor):
    return tuple(max(0, int(c * factor)) for c in rgb)


# --- palettes (placeholders — see module docstring) -------------------------

RAIN_STOPS = [(255, 255, 255), (0, 255, 135), (0, 180, 0), (0, 80, 0), (0, 20, 0)]
PULSE_STOPS = [(255, 255, 255), (140, 210, 255), (50, 130, 230), (15, 55, 110), (0, 10, 30)]


# =============================================================================
# Foreground — deliberately simplified, just enough to judge contrast against
# the background variants. Not production quality.
# =============================================================================

class RainForeground:
    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.heads = [random.uniform(-rows, 0) for _ in range(cols)]
        self.speeds = [random.uniform(0.35, 0.9) for _ in range(cols)]
        self.trails = [random.randint(8, 20) for _ in range(cols)]
        self.char_cache = {}

    def update(self):
        for x in range(self.cols):
            self.heads[x] += self.speeds[x]
            if self.heads[x] - self.trails[x] > self.rows:
                self.heads[x] = random.uniform(-30, -5)
                self.speeds[x] = random.uniform(0.35, 0.9)
                self.trails[x] = random.randint(8, 20)
                for y in range(self.rows):
                    self.char_cache.pop((x, y), None)

    def draw(self, grid):
        for x in range(self.cols):
            head = self.heads[x]
            trail = self.trails[x]
            for y in range(max(0, int(head - trail)), min(self.rows, int(head) + 1)):
                distance = head - y
                if distance < 0 or distance > trail:
                    continue
                t = distance / trail
                key = (x, y)
                if key not in self.char_cache:
                    self.char_cache[key] = random.choice(KATAKANA)
                grid[y][x] = (self.char_cache[key], gradient(RAIN_STOPS, t))


class PulseForeground:
    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.cx, self.cy = cols / 2.0, rows / 2.0
        self.max_radius = math.hypot(self.cx, self.cy)
        self.frame = 0

    def update(self):
        self.frame += 1

    @property
    def phase(self):
        return self.frame * 0.4

    def draw(self, grid):
        for ring in range(4):
            radius = (self.phase + ring * (self.max_radius / 4)) % self.max_radius
            t = radius / self.max_radius  # 0 near center (new) -> 1 at edge (fading)
            for y in range(self.rows):
                for x in range(self.cols):
                    d = math.hypot((x - self.cx) * 0.5, y - self.cy)
                    if abs(d - radius) < 0.6:
                        grid[y][x] = ("o", gradient(PULSE_STOPS, t))


# =============================================================================
# Background variants — the actual question being prototyped.
# =============================================================================

class RainBgGhost:
    """A — a second, dimmer, slower rain layer offset in phase."""

    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.heads = [random.uniform(-rows, 0) for _ in range(cols)]
        self.speeds = [random.uniform(0.08, 0.2) for _ in range(cols)]
        self.trails = [random.randint(4, 9) for _ in range(cols)]
        self.active = [random.random() < 0.35 for _ in range(cols)]  # sparse
        self.char_cache = {}

    def update(self):
        for x in range(self.cols):
            if not self.active[x]:
                continue
            self.heads[x] += self.speeds[x]
            if self.heads[x] - self.trails[x] > self.rows:
                self.heads[x] = random.uniform(-30, -5)

    def draw(self, grid):
        for x in range(self.cols):
            if not self.active[x]:
                continue
            head = self.heads[x]
            trail = self.trails[x]
            for y in range(max(0, int(head - trail)), min(self.rows, int(head) + 1)):
                distance = head - y
                if distance < 0 or distance > trail:
                    continue
                t = distance / trail
                key = (x, y)
                if key not in self.char_cache:
                    self.char_cache[key] = random.choice(KATAKANA)
                color = dim(gradient(RAIN_STOPS, min(1.0, t + 0.4)), 0.35)
                grid[y][x] = (self.char_cache[key], color)


class RainBgFog:
    """B — a static field of very dim characters that breathe (fade in/out)."""

    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        count = max(20, (cols * rows) // 40)
        self.points = [
            (random.randrange(cols), random.randrange(rows), random.choice(KATAKANA), random.uniform(0, math.tau))
            for _ in range(count)
        ]
        self.frame = 0

    def update(self):
        self.frame += 1

    def draw(self, grid):
        for x, y, ch, phase in self.points:
            brightness = 0.06 + 0.10 * (0.5 + 0.5 * math.sin(self.frame * 0.03 + phase))
            grid[y][x] = (ch, dim(RAIN_STOPS[2], brightness / 0.15))


class RainBgWash:
    """C — pure background color gradient, no characters."""

    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows

    def update(self):
        pass

    def draw(self, grid_bg):
        for y in range(self.rows):
            t = y / max(1, self.rows - 1)
            color = dim(gradient([(0, 25, 0), (0, 4, 0), (0, 0, 0)], t), 1.0)
            for x in range(self.cols):
                grid_bg[y][x] = color


class PulseBgEcho:
    """A — a slower, dimmer set of rings behind the main pulse."""

    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.cx, self.cy = cols / 2.0, rows / 2.0
        self.max_radius = math.hypot(self.cx, self.cy)
        self.frame = 0

    def update(self):
        self.frame += 1

    def draw(self, grid):
        phase = self.frame * 0.15
        for ring in range(3):
            radius = (phase + ring * (self.max_radius / 3)) % self.max_radius
            t = radius / self.max_radius
            for y in range(self.rows):
                for x in range(self.cols):
                    d = math.hypot((x - self.cx) * 0.5, y - self.cy)
                    if abs(d - radius) < 0.8:
                        grid[y][x] = (".", dim(gradient(PULSE_STOPS, min(1.0, t + 0.3)), 0.35))


class PulseBgStars:
    """B — particles radiating outward from center, own depth/speed (à la Network)."""

    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.cx, self.cy = cols / 2.0, rows / 2.0
        self.stars = [
            [random.uniform(0, math.tau), random.uniform(0.05, 1.0), random.uniform(0.10, 0.35)]
            for _ in range(max(30, (cols * rows) // 25))
        ]

    def update(self):
        for star in self.stars:
            star[1] += star[2] * 0.02
            if star[1] > 1.0:
                star[0] = random.uniform(0, math.tau)
                star[1] = 0.05
                star[2] = random.uniform(0.10, 0.35)

    def draw(self, grid):
        max_r = math.hypot(self.cx, self.cy)
        for angle, depth, _ in self.stars:
            r = depth * max_r
            x = int(self.cx + math.cos(angle) * r * 2)
            y = int(self.cy + math.sin(angle) * r)
            if 0 <= x < self.cols and 0 <= y < self.rows:
                grid[y][x] = (".", dim(gradient(PULSE_STOPS, depth), 0.5))


class PulseBgWash:
    """C — radial gradient that breathes in sync with the pulse phase."""

    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.cx, self.cy = cols / 2.0, rows / 2.0
        self.max_radius = math.hypot(self.cx, self.cy)
        self.frame = 0

    def update(self):
        self.frame += 1

    def draw(self, grid_bg):
        breath = 0.5 + 0.5 * math.sin(self.frame * 0.05)
        for y in range(self.rows):
            for x in range(self.cols):
                d = math.hypot((x - self.cx) * 0.5, y - self.cy) / self.max_radius
                t = max(0.0, min(1.0, d - breath * 0.3))
                color = dim(gradient([(0, 15, 35), (0, 3, 10), (0, 0, 0)], t), 1.0)
                grid_bg[y][x] = color


FOREGROUND = {"rain": RainForeground, "pulse": PulseForeground}
BACKGROUND = {
    ("rain", "A"): RainBgGhost,
    ("rain", "B"): RainBgFog,
    ("rain", "C"): RainBgWash,
    ("pulse", "A"): PulseBgEcho,
    ("pulse", "B"): PulseBgStars,
    ("pulse", "C"): PulseBgWash,
}
# C variants paint a background wash (no chars); A/B paint dim characters.
WASH_VARIANTS = {"C"}


# =============================================================================
# Terminal plumbing — raw mode input, true color output, no curses.
# =============================================================================

def read_key(timeout):
    r, _, _ = select.select([sys.stdin], [], [], timeout)
    if not r:
        return None
    ch = sys.stdin.read(1)
    if ch == "\x1b":
        r2, _, _ = select.select([sys.stdin], [], [], 0.05)
        if not r2:
            return "ESC"
        ch2 = sys.stdin.read(1)
        # "[" is the common CSI introducer; "O" is what some terminals send
        # for arrow keys in "application cursor keys" mode (DECCKM) — accept
        # both instead of assuming one.
        if ch2 in ("[", "O"):
            r3, _, _ = select.select([sys.stdin], [], [], 0.05)
            if r3:
                ch3 = sys.stdin.read(1)
                if ch3 == "C":
                    return "RIGHT"
                if ch3 == "D":
                    return "LEFT"
        return "ESC"
    return ch


def render(cols, rows, fg_grid, bg_grid, status):
    out = [move(0, 0)]
    last_color = None
    for y in range(rows):
        out.append(move(y, 0))
        last_color = None
        for x in range(cols):
            if y == rows - 1 and x == cols - 1:
                # The bottom-right corner: writing here makes most terminals
                # auto-wrap and scroll the whole screen up a line (no "next
                # line" to wrap to) — the blank-line-at-bottom glitch. curses
                # dodges this by swallowing the error on that exact cell
                # (see AGENTS.md); we just skip drawing it, same effect.
                continue
            cell = fg_grid[y][x]
            if cell is not None:
                ch, rgb = cell
                # Full-width Katakana render as 2 terminal cells in most
                # fonts, but our grid is 1 cell = 1 logical position. Relying
                # on the terminal's auto cursor-advance after such a glyph
                # drifts every following cell on the row right by one column
                # — a *prototype-only* artifact from writing a whole row in
                # one shot. Re-anchoring the cursor before every character
                # (what curses' addch/addstr-at-position does in the real
                # app) removes the drift entirely.
                out.append(move(y, x))
                color = ("fg", rgb)
                if color != last_color:
                    out.append(fg(rgb) + f"{CSI}49m")
                    last_color = color
                out.append(ch)
                last_color = None  # position no longer trustworthy after a glyph; force next re-anchor
            else:
                rgb = bg_grid[y][x]
                if rgb is not None:
                    color = ("bg", rgb)
                    if color != last_color:
                        out.append(bg(rgb))
                        last_color = color
                    out.append(" ")
                else:
                    if last_color is not None:
                        out.append(RESET)
                        last_color = None
                    out.append(" ")
    out.append(RESET)
    out.append(move(0, 0) + f"{CSI}7m {status} {CSI}0m")
    sys.stdout.write("".join(out))
    sys.stdout.flush()


def main():
    cols, rows = os.get_terminal_size()
    mode_i, variant_i = 0, 0
    mode = MODES[mode_i]
    variant = VARIANTS[variant_i]

    foreground = FOREGROUND[mode](cols, rows)
    background = BACKGROUND[(mode, variant)](cols, rows)

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    sys.stdout.write(ALT_ON + HIDE_CURSOR)
    tty.setcbreak(fd)

    try:
        frame_dt = 0.04
        last_raw = ""
        while True:
            t0 = time.time()

            foreground.update()
            background.update()

            fg_grid = [[None] * cols for _ in range(rows)]
            bg_grid = [[None] * cols for _ in range(rows)]
            if variant in WASH_VARIANTS:
                background.draw(bg_grid)
            else:
                background.draw(fg_grid)
            foreground.draw(fg_grid)

            status = (
                f"[m] mode: {mode.upper()}   [a/d or <-/->] variant: {variant} — {VARIANT_NAMES[variant]}"
                f"   [q] quit   last key: {last_raw!r}"
            )
            render(cols, rows, fg_grid, bg_grid, status)

            key = read_key(max(0.0, frame_dt - (time.time() - t0)))
            if key is not None:
                last_raw = key
            if key in ("q", "Q", "ESC"):
                break
            elif key in ("m", "M"):
                mode_i = (mode_i + 1) % len(MODES)
                mode = MODES[mode_i]
                foreground = FOREGROUND[mode](cols, rows)
                background = BACKGROUND[(mode, variant)](cols, rows)
            elif key in ("RIGHT", "d", "D"):
                variant_i = (variant_i + 1) % len(VARIANTS)
                variant = VARIANTS[variant_i]
                background = BACKGROUND[(mode, variant)](cols, rows)
            elif key in ("LEFT", "a", "A"):
                variant_i = (variant_i - 1) % len(VARIANTS)
                variant = VARIANTS[variant_i]
                background = BACKGROUND[(mode, variant)](cols, rows)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write(RESET + SHOW_CURSOR + ALT_OFF)
        sys.stdout.flush()


if __name__ == "__main__":
    if not sys.stdout.isatty():
        print("This prototype needs a real terminal.", file=sys.stderr)
        sys.exit(1)
    main()
