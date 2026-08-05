"""True-color engine: gradient math, RGB<->ANSI conversion, and automatic
fallback to the existing 256-color palette when the terminal doesn't
advertise truecolor support.

Pure functions only — no curses, no I/O — so this module is fully
unit-testable (see tests/test_color.py). Drawing to the actual terminal
lives in core/screen.py, which is the only place that writes these
sequences to stdout.
"""

import os

# The 16 standard/high-intensity xterm colors (indices 0-15), as RGB. These
# are conventional approximations (there's no single authoritative mapping —
# terminals theme these), matching common xterm/VTE defaults.
_STANDARD_16_RGB = [
    (0, 0, 0), (205, 0, 0), (0, 205, 0), (205, 205, 0),
    (0, 0, 238), (205, 0, 205), (0, 205, 205), (229, 229, 229),
    (127, 127, 127), (255, 0, 0), (0, 255, 0), (255, 255, 0),
    (92, 92, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255),
]

# The 6 valid component values in the xterm 256-color 6x6x6 cube (indices
# 16-231). Used both to build a cube index's RGB and to snap an arbitrary
# RGB down to the nearest cube coordinate.
_CUBE_SCALE = (0, 95, 135, 175, 215, 255)


def supports_truecolor(env=None) -> bool:
    """Detect true color (24-bit) support from the COLORTERM env var.

    Recognizes 'truecolor' and '24bit' (case-insensitive) — what terminals
    that actually support 24-bit color set. Anything else, including
    COLORTERM being unset entirely, means: fall back to 256-color.
    """
    if env is None:
        env = os.environ
    value = env.get('COLORTERM', '').strip().lower()
    return value in ('truecolor', '24bit')


def gradient(stops, t: float):
    """Interpolate an RGB tuple along a piecewise-linear gradient.

    `stops` is a non-empty list of (r, g, b) control points, evenly spaced
    across t in [0, 1]. `t` outside that range is clamped.
    """
    if not stops:
        raise ValueError('gradient() requires at least one stop')
    if len(stops) == 1:
        return stops[0]

    t = max(0.0, min(1.0, t))
    segments = len(stops) - 1
    position = t * segments
    index = min(int(position), segments - 1)
    local_t = position - index
    a, b = stops[index], stops[index + 1]
    return (
        int(round(a[0] + (b[0] - a[0]) * local_t)),
        int(round(a[1] + (b[1] - a[1]) * local_t)),
        int(round(a[2] + (b[2] - a[2]) * local_t)),
    )


def dim(rgb, factor: float):
    """Scale an RGB color's brightness by `factor` (clamped to >= 0)."""
    factor = max(0.0, factor)
    return tuple(max(0, min(255, int(round(channel * factor)))) for channel in rgb)


def index256_to_rgb(index: int):
    """Convert an xterm 256-color palette index to its approximate RGB.

    Covers all three regions: the 16 standard/high-intensity colors
    (0-15), the 6x6x6 color cube (16-231), and the grayscale ramp
    (232-255). This is the single source of truth used to derive
    continuous gradient stops from core.palette.COLOR_PALETTE's existing
    index tables, instead of hand-duplicating RGB values per theme.
    """
    if not (0 <= index <= 255):
        raise ValueError('xterm 256-color index must be 0-255, got {0}'.format(index))

    if index < 16:
        return _STANDARD_16_RGB[index]

    if index < 232:
        cube_index = index - 16
        r = cube_index // 36
        g = (cube_index % 36) // 6
        b = cube_index % 6
        return (_CUBE_SCALE[r], _CUBE_SCALE[g], _CUBE_SCALE[b])

    # Grayscale ramp: 232 (darkest) .. 255 (lightest), step of 10.
    level = 8 + (index - 232) * 10
    return (level, level, level)


def nearest_256(rgb) -> int:
    """Deterministically snap an RGB tuple to the nearest xterm-256 index.

    Checks both the 6x6x6 color cube and the grayscale ramp (most of our
    darker shades land there) and returns whichever is closer by squared
    Euclidean distance. Ties resolve to the cube index — stable and
    deterministic, as required by the project's testing conventions.
    """
    r, g, b = rgb

    def nearest_cube_component(value):
        return min(range(6), key=lambda i: abs(_CUBE_SCALE[i] - value))

    cube_index = (
        16
        + (36 * nearest_cube_component(r))
        + (6 * nearest_cube_component(g))
        + nearest_cube_component(b)
    )
    cube_distance = _distance_sq(rgb, index256_to_rgb(cube_index))

    gray_level = (r + g + b) / 3.0
    gray_step = max(0, min(23, int(round((gray_level - 8) / 10.0))))
    gray_index = 232 + gray_step
    gray_distance = _distance_sq(rgb, index256_to_rgb(gray_index))

    return gray_index if gray_distance < cube_distance else cube_index


def _distance_sq(a, b) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def ansi_fg(rgb, truecolor: bool) -> str:
    """ANSI SGR sequence to set the foreground color to `rgb`.

    True color (24-bit) when supported; otherwise snapped to the nearest
    256-color index via `nearest_256` and emitted as a standard 256-color
    sequence — the fallback floor the project's existing palette defines.
    """
    if truecolor:
        r, g, b = rgb
        return '\x1b[38;2;{0};{1};{2}m'.format(r, g, b)
    return '\x1b[38;5;{0}m'.format(nearest_256(rgb))
