# Matrix Rain 🎬

A terminal-based Matrix digital rain animation featuring Japanese characters (Katakana), numbers, and symbols - just like in the movie!

![Matrix Rain](https://media.giphy.com/media/sULKEgDMX8LcI/giphy.gif)

## Features

- 🇯🇵 **Authentic Japanese characters** - Half-width and full-width Katakana
- 🎨 **Multiple colors** - Green, red, blue, cyan, magenta, yellow, white
- 🌈 **Rainbow mode** - Psychedelic cycling colors
- ⚡ **Adjustable speed** - From slow and dramatic to blazing fast
- 📊 **Density control** - Sparse or dense rain
- 🖥️ **Screensaver mode** - Exit on any keypress
- 📐 **Terminal resize support** - Adapts to window size changes
- ✨ **Character mutation** - Characters randomly change as they fall (like the movie!)

## Installation

The script is already installed at `~/bin/matrix-rain`.

Make sure `~/bin` is in your PATH. For Fish shell, add to `~/.config/fish/config.fish`:

```fish
if test -d ~/bin
    if not contains -- ~/bin $PATH
        set -p PATH ~/bin
    end
end
```

## Usage

```bash
# Classic green Matrix rain
matrix-rain

# Different colors
matrix-rain --color red
matrix-rain --color cyan
matrix-rain -c magenta

# Rainbow mode!
matrix-rain --rainbow
matrix-rain -r

# Speed control (1-10, default: 5)
matrix-rain --speed 8      # Faster
matrix-rain -s 2           # Slower

# Density control (1-10, default: 5)
matrix-rain --density 8    # Dense rain
matrix-rain -d 3           # Sparse rain

# Screensaver mode (exit on any keypress)
matrix-rain --screensaver
matrix-rain -S

# Combine options
matrix-rain -c cyan -s 7 -d 8 -S
matrix-rain --rainbow --speed 6 --density 7
```

## Options

| Flag | Long | Description | Default |
|------|------|-------------|---------|
| `-c` | `--color` | Rain color (green/red/blue/cyan/magenta/yellow/white/rainbow) | green |
| `-s` | `--speed` | Animation speed (1-10) | 5 |
| `-d` | `--density` | Rain density (1-10) | 5 |
| `-S` | `--screensaver` | Exit on any keypress | off |
| `-r` | `--rainbow` | Rainbow color mode | off |
| `-h` | `--help` | Show help message | - |

## Controls

- Press `q` or `Escape` to exit
- In screensaver mode (`-S`), press any key to exit
- `Ctrl+C` also works to exit

## Requirements

- Python 3.6+
- Terminal with Unicode/UTF-8 support
- A font that supports Japanese characters (e.g., Noto Sans CJK, Hack Nerd Font)

## Character Sets

The script uses authentic Matrix-style characters:

- **Half-width Katakana**: ｦｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄ...
- **Full-width Katakana**: アイウエオカキクケコサシスセソ...
- **Numbers**: 0123456789
- **Symbols**: !@#$%^&*()_+-=[]{}|;:',.<>?
- **Latin**: ABCDEFGHIJKLMNOPQRSTUVWXYZ

## License

MIT License - Feel free to use, modify, and distribute!

## Credits

Created with Claude 🤖
