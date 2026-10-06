# Matrix Rain 🎬

A beautiful terminal-based Matrix digital rain animation featuring authentic Japanese characters (Katakana), smooth color gradients, and cinematic visual effects - just like in the movie!

<p align="center">
  <img src="assets/rain.gif" alt="Matrix Rain: green Katakana rain with white glowing heads" width="640">
</p>

## Features

- **Authentic Japanese Characters** - Half-width and full-width Katakana (ｦｱｲｳｴｵ / アイウエオ)
- **8-Shade Color Gradients** - Smooth transitions from bright white head → vibrant color → fade to dark
- **Glowing Head Effect** - White leading character with 3-character bright glow trail
- **11 Color Themes** - Classic and neon palettes, including Orange, Pink, Ice, and Violet (see the [gallery](#available-colors))
- **Rainbow Mode** - Psychedelic cycling colors across columns
- **3 Visualizer Modes** - Rain, Pulse, and Network, switchable live with `m`
- **True Color** - 24-bit gradients where the terminal supports it, with an automatic 256-color fallback
- **Video Wall** - Several terminals on one machine become tiles of a single screen (see [Video wall](#video-wall))
- **Adjustable Speed** - From slow cinematic (1) to blazing fast (10)
- **Density Control** - From sparse (1) to very dense (10)
- **Screensaver Mode** - Exit on any keypress
- **Full Terminal Coverage** - Rain reaches every corner of your screen
- **Smooth Animation** - Column-based rendering with no flickering
- **Terminal Resize Support** - Adapts dynamically to window size changes

## Installation

### Quick Install

```bash
# Clone the repository
git clone https://github.com/Serg-Ale/matrix-rain.git

# Make it executable
chmod +x matrix-rain/matrix-rain

# Option 1: Run directly
./matrix-rain/matrix-rain

# Option 2: Add to your PATH (recommended)
mkdir -p ~/bin
ln -sf "$(pwd)/matrix-rain/matrix-rain" ~/bin/matrix-rain
```

### Add to PATH

**Fish shell** (`~/.config/fish/config.fish`):
```fish
if test -d ~/bin
    if not contains -- ~/bin $PATH
        set -p PATH ~/bin
    end
end
```

**Bash/Zsh** (`~/.bashrc` or `~/.zshrc`):
```bash
export PATH="$HOME/bin:$PATH"
```

## Usage

```bash
# Classic green Matrix rain (default)
matrix-rain

# Different colors
matrix-rain -c red
matrix-rain -c cyan
matrix-rain -c blue
matrix-rain -c magenta
matrix-rain -c yellow
matrix-rain -c white

# Rainbow mode!
matrix-rain --rainbow

# Start straight in a different visualizer (default: rain)
matrix-rain -m pulse
matrix-rain -m network

# Adjust speed (1-10, default: 5)
matrix-rain -s 8      # Faster
matrix-rain -s 2      # Slower, more dramatic

# Adjust density (1-10, default: 7)
matrix-rain -d 10     # Maximum density
matrix-rain -d 3      # Sparse rain

# Screensaver mode (exit on any keypress)
matrix-rain -S

# Combine options for custom experience
matrix-rain -c green -s 6 -d 9      # Fast, very dense green
matrix-rain -c cyan -s 3 -d 5 -S    # Slow cyan screensaver
matrix-rain -m network --rainbow -s 7 -d 8  # Fast dense rainbow network
```

## Command Line Options

| Flag | Long Form | Description | Default |
|------|-----------|-------------|---------|
| `-c` | `--color` | Rain color theme | `green` |
| `-m` | `--mode` | Starting visualizer (`rain`, `pulse`, `network`) | `rain` |
| `-s` | `--speed` | Animation speed (1-10) | `5` |
| `-d` | `--density` | Rain density (1-10) | `7` |
| `-S` | `--screensaver` | Exit on any keypress | `off` |
| `-r` | `--rainbow` | Rainbow color cycling mode | `off` |
| | `--at` | `ROW,COL` — where this terminal sits on the wall's grid; implies `--wall` | queue by arrival |
| | `--wall` | Join (or start) a video wall with other terminals — see [Video wall](#video-wall) | `off` |
| `-h` | `--help` | Show help message | - |

Rainbow mode is its own flag (`-r`/`--rainbow`), not a `--color` value — it
cycles through every theme below rather than picking one.

## Video wall

Run `matrix-rain --wall` in two or more terminals on the same machine and they
become tiles of one big screen: the animation runs once, across all of them.
The first terminal becomes the host; the others join it, side by side in the
order they open. Theme, mode, rainbow, speed and density are shared — change them in
any tile and every tile follows.

```bash
matrix-rain --wall -c cyan    # first terminal: starts the wall
matrix-rain --wall            # second, third...: join it
```

<p align="center">
  <img src="assets/wall-row.gif" alt="Two terminals side by side showing one Network animation that continues across both windows" width="800">
</p>
<p align="center"><em>Two terminals, one Network scene (rainbow). Each window shows its half of the same canvas.</em></p>

If your terminals aren't in a single row, say where each one sits with
`--at ROW,COL` (row 0 is the top, column 0 the left). For one terminal on top
and two below:

```bash
matrix-rain --at 0,0 -c cyan    # top (starts the wall)
matrix-rain --at 1,0            # bottom left
matrix-rain --at 1,1            # bottom right
```

<p align="center">
  <img src="assets/wall-grid.gif" alt="Three terminals in a grid: Rain streams run from the top window down into the two below" width="800">
</p>
<p align="center"><em>A 2D grid: the rain streams pass from the top window into the two below it.</em></p>

Rows stack top to bottom and tiles in a row go left to right by column. Tiles
of different sizes line up along the top of their row, and a row as wide as
its widest tile — keep the rows about the same total width, since any
difference is simply blank. While the control panel is visible (`p` toggles
it), each tile shows its own `WALL rXcY` badge in the corner. Terminals that
don't pass `--at` queue up in row 0 in the order they join.

Reorganizing doesn't need a restart: press `L` in a tile to enter layout mode,
and its arrow keys move that tile around the grid (moving onto another tile
swaps the two); press `L` again to leave the mode. While it's on, every tile
gets seam guides and the badge shows `LAYOUT rXcY`. Outside layout mode the
arrows adjust speed and density as usual. If a terminal joins with an `--at`
already taken, it gets that spot and the tile that was there steps aside to the
next free column of its row.

<p align="center">
  <img src="assets/wall-layout.png" alt="Layout mode: magenta guides outline each tile and the badge reads LAYOUT r0c0" width="800">
</p>
<p align="center"><em>Layout mode: guides outline every tile, and the badge shows which one you're moving.</em></p>

Real windows have frames, and the picture breaks at the seam. In the wall, the
gap keys hide a few columns or rows of the canvas at each seam, so the image
reads as continuous behind the frame: `>` / `<` widen / narrow the horizontal
gap (in columns), `}` / `{` the vertical one (in rows). It starts at 0 and the
right value depends on your terminal and font, so adjust it by eye while
watching a seam. The panel shows the current values, and the setting lasts for
the session only.

You don't have to start in the wall: press `J` in any running terminal to join
(or start) it, and `J` again to leave. Joining adopts the wall's theme, mode,
speed and density; leaving keeps whatever the wall had at that moment, with the
animation starting over. Closing the first terminal doesn't end the wall:
when the host goes away (`q`, `Ctrl+C`, a crash, or leaving with `J`), the
oldest remaining tile takes over as host with the wall's last settings
(theme, mode, speed, density and gap) and the others reconnect to it. The
animation starts over, but the picture carries on. Tile positions you moved
with layout mode aren't carried over — tiles go back to the `--at` they
declared.

`q` or `Esc` quits that terminal, whether it's the host or not.
`--wall` can't be combined with `-S`. The wall is local to your user on this
machine (a private Unix socket); it doesn't connect across machines.

### Available Colors

<p align="center">
  <img src="assets/themes.png" alt="Rain in nine of the color themes, plus rainbow mode" width="760">
</p>

| Color | Description |
|-------|-------------|
| `green` | Classic Matrix green (default) |
| `red` | Red theme |
| `blue` | Blue theme |
| `cyan` | Cyan/teal theme |
| `magenta` | Purple/magenta theme |
| `yellow` | Yellow/gold theme |
| `white` | Grayscale theme |
| `orange` | Warm amber theme |
| `pink` | Neon pink theme |
| `ice` | Icy blue theme |
| `violet` | Deep violet theme |

## Controls

| Key | Action |
|-----|--------|
| `q` | Quit |
| `Escape` | Quit |
| `Ctrl+C` | Quit |
| Any key | Quit (in screensaver mode only) |

### Live Customization

Outside screensaver mode, adjust the animation without restarting it:

| Key | Action |
|-----|--------|
| `W` / `↑` / `+` | Increase speed |
| `S` / `↓` / `-` | Decrease speed |
| `D` / `→` / `]` | Increase density (more streams) |
| `A` / `←` / `[` | Decrease density (fewer streams) |
| `t` | Cycle through color themes |
| `r` | Toggle rainbow mode |
| `j` | Join / leave the video wall |
| `l` | Layout mode (in the wall): arrows move this tile |
| `<` `>` / `{` `}` | Wall seam gap: narrower / wider, horizontal / vertical |
| `m` | Cycle visualizers: Rain, Pulse, Network |
| `,` / `.` | Decrease/increase Network tempo (Network mode) or Pulse ring thickness (Pulse mode) |
| `p` | Hide/show the live-control panel |
| `h` / `?` | Show the control panel |

<p align="center">
  <img src="assets/panel.png" alt="The live-control panel over the rain" width="640">
</p>

The persistent, btop-inspired panel shows the selected theme plus speed and
density meters. It is hidden automatically in screensaver mode and on terminals
that are too small to render it safely.

## Visualizer Modes

Press `m` while running to cycle through the available hacker-style animations:

| Mode | Visual |
|------|--------|
| `RAIN` | The classic falling Katakana rain |
| `PULSE` | Expanding ASCII energy rings from the screen centre |
| `NETWORK` | A 3D point cloud with branches, packets, and complementary filled faces |

**Rain** is the default (the animation at the top of this page).

**Pulse** sends expanding rings of characters out from the screen centre, over plain black:

<p align="center">
  <img src="assets/pulse.gif" alt="Pulse: expanding cyan rings of Katakana" width="640">
</p>

**Network** is a slowly turning 3D point cloud with branches, packets, and
complementary filled faces (shown here in violet):

<p align="center">
  <img src="assets/network.gif" alt="Network: a 3D point cloud with links and traveling packets" width="640">
</p>

Your selected color theme, rainbow mode, speed, and density apply to every
visualizer. Density changes the number of rain streams, pulse rings, or network
nodes depending on the active mode.

The Network visualizer is intentionally slowed down: global speed `10` matches
the previous Network pace at global speed `2`. Use `,` and `.` to adjust its
Network-only multiplier from `0.1x` through `1.0x`, in `0.1x` steps.

## Requirements

- **Python 3.6+** (uses `curses`, `dataclasses`)
- **True color or 256-color terminal** (true color is detected from `COLORTERM`; everything falls back to the 256-color palette otherwise)
- **UTF-8 support** for Japanese characters
- **Monospace font with Japanese support** (e.g., Noto Sans Mono CJK, Hack Nerd Font, JetBrains Mono)

### Tested Terminals

- Konsole (KDE)
- GNOME Terminal
- Alacritty
- Kitty
- xterm (with UTF-8)
- Windows Terminal (WSL)

## How It Works

### Character Sets

The animation uses authentic Matrix-style characters:

```
Half-width Katakana: ｦｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ
Full-width Katakana: アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホ...
Numbers & Symbols:   0123456789:<>*+=-@#$%&
```

### Color Gradient System

Each trail uses an 8-shade gradient for smooth, cinematic fading:

```
Shade 0: ████ Bright White    (head)
Shade 1: ████ Bright Glow     (glow zone)
Shade 2: ████ Medium Glow     (glow zone)
Shade 3: ████ Bright Color    (trail start)
Shade 4: ████ Medium-Bright   
Shade 5: ████ Medium          
Shade 6: ████ Dim             
Shade 7: ████ Very Dark       (trail end)
```

### Architecture

- **Column-based rendering** - Each column independently tracks its rain drop
- **Persistent character grid** - Characters stay in place (no horizontal flickering)
- **Brightness grid** - Separate tracking of fade levels for smooth gradients
- **Continuous color engine** - Gradients are interpolated in RGB and written as raw ANSI, in 24-bit when the terminal supports it and snapped to the nearest xterm-256 index when it doesn't

## Troubleshooting

### Japanese characters not displaying

Make sure your terminal font supports Japanese characters. Recommended fonts:
- Noto Sans Mono CJK
- Hack Nerd Font
- Source Han Code JP
- JetBrains Mono (with fallback)

### Colors look wrong

Ensure your terminal supports 256 colors:
```bash
echo $TERM          # Should show xterm-256color or similar
tput colors         # Should show 256
```

### Characters not reaching bottom of screen

Update to the latest version - this was fixed in commit `34d795b`.

## License

MIT License - Feel free to use, modify, and distribute!

## Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest new features
- Submit pull requests

## Credits

Created by [Serg-Ale](https://github.com/Serg-Ale) with assistance from Claude AI

---

<p align="center">
  <i>"Unfortunately, no one can be told what the Matrix is. You have to see it for yourself."</i>
  <br>
  - Morpheus
</p>
