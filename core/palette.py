"""256-color palette definitions.

This is the pre-true-color engine: fixed 8-shade gradients addressed as
xterm 256-color indices. True color with automatic fallback to this
palette is ticket #3 — this module stays as the fallback target once that
lands, so its shape (8 shades per theme, index 0 = white head) is a
contract other code depends on, not just current behavior.

256-color palette structure:
    0-7:     Standard colors (black, red, green, yellow, blue, magenta, cyan, white)
    8-15:    High-intensity colors
    16-231:  6x6x6 color cube (216 colors)
    232-255: Grayscale (24 shades, dark to light)

Color cube formula: 16 + (36 x r) + (6 x g) + b, where r,g,b are 0-5
"""

# Number of brightness levels
NUM_SHADES = 8

# Pre-defined color indices for each theme using 256-color palette
# Each theme has 8 shades: [head(white), glow1, glow2, bright, medium, dim, dark, very_dark]
COLOR_PALETTE = {
    'green': [
        15,   # 0: Bright white (head)
        48,   # 1: #00ff87 - very bright green/white glow
        41,   # 2: #00d75f - bright green glow
        40,   # 3: #00d700 - bright green
        34,   # 4: #00af00 - medium-bright green
        28,   # 5: #008700 - medium green
        22,   # 6: #005f00 - dark green
        236,  # 7: #303030 - very dark (almost black)
    ],
    'red': [
        15,   # 0: Bright white (head)
        210,  # 1: #ff8787 - very bright red/white glow
        203,  # 2: #ff5f5f - bright red glow
        196,  # 3: #ff0000 - bright red
        160,  # 4: #d70000 - medium-bright red
        124,  # 5: #af0000 - medium red
        88,   # 6: #870000 - dark red
        236,  # 7: #303030 - very dark
    ],
    'blue': [
        15,   # 0: Bright white (head)
        117,  # 1: #87d7ff - very bright blue/white glow
        75,   # 2: #5fafff - bright blue glow
        33,   # 3: #0087ff - bright blue
        27,   # 4: #005fff - medium-bright blue
        21,   # 5: #0000ff - medium blue
        19,   # 6: #0000af - dark blue
        236,  # 7: #303030 - very dark
    ],
    'cyan': [
        15,   # 0: Bright white (head)
        123,  # 1: #87ffff - very bright cyan/white glow
        87,   # 2: #5fffff - bright cyan glow
        51,   # 3: #00ffff - bright cyan
        44,   # 4: #00d7d7 - medium-bright cyan
        37,   # 5: #00afaf - medium cyan
        30,   # 6: #008787 - dark cyan
        236,  # 7: #303030 - very dark
    ],
    'magenta': [
        15,   # 0: Bright white (head)
        219,  # 1: #ffafff - very bright magenta/white glow
        213,  # 2: #ff87ff - bright magenta glow
        201,  # 3: #ff00ff - bright magenta
        165,  # 4: #d700ff - medium-bright magenta
        129,  # 5: #af00ff - medium magenta
        93,   # 6: #8700ff - dark magenta
        236,  # 7: #303030 - very dark
    ],
    'yellow': [
        15,   # 0: Bright white (head)
        228,  # 1: #ffff87 - very bright yellow/white glow
        227,  # 2: #ffff5f - bright yellow glow
        226,  # 3: #ffff00 - bright yellow
        220,  # 4: #ffd700 - medium-bright yellow
        178,  # 5: #d7af00 - medium yellow
        136,  # 6: #af8700 - dark yellow/gold
        236,  # 7: #303030 - very dark
    ],
    'white': [
        15,   # 0: Bright white (head)
        255,  # 1: #eeeeee - very bright white
        253,  # 2: #dadada - bright white
        251,  # 3: #c6c6c6 - light gray
        246,  # 4: #949494 - medium gray
        242,  # 5: #6c6c6c - dim gray
        238,  # 6: #444444 - dark gray
        235,  # 7: #262626 - very dark gray
    ],
    'orange': [
        15, 230, 223, 214, 208, 166, 94, 236,
    ],
    'pink': [
        15, 225, 218, 205, 198, 162, 89, 236,
    ],
    'ice': [
        15, 195, 159, 81, 39, 31, 24, 236,
    ],
    'violet': [
        15, 189, 147, 99, 63, 57, 54, 236,
    ],
}

# Rainbow colors sequence
RAINBOW_SEQUENCE = ['red', 'yellow', 'green', 'cyan', 'blue', 'magenta']

# Curses color pair reserved for the network mode's complementary fill color.
CONTRAST_PAIR = 60
CONTRAST_COLORS = {
    'green': 93, 'red': 51, 'blue': 226, 'cyan': 196, 'magenta': 46,
    'yellow': 27, 'white': 39, 'orange': 33, 'pink': 51, 'ice': 201,
    'violet': 226,
}
