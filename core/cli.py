"""Command-line entry point: argument parsing and the curses bootstrap."""

import curses
import sys

from .app import App
from .palette import COLOR_PALETTE


def parse_args(argv=None):
    """Parse command line arguments."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Matrix Rain - Terminal Digital Rain Effect',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  matrix-rain                     # Classic green Matrix rain
  matrix-rain -c cyan             # Cyan colored rain
  matrix-rain -c red -s 8         # Fast red rain
  matrix-rain --rainbow           # Rainbow mode!
  matrix-rain -S                  # Screensaver mode (exit on keypress)
  matrix-rain -c green -s 6 -d 9  # Fast, very dense green rain

Colors available: green, red, blue, cyan, magenta, yellow, white, orange, pink, ice, violet, rainbow

Press 'q' or Escape to exit (or any key in screensaver mode).
        '''
    )

    parser.add_argument(
        '-c', '--color',
        type=str,
        default='green',
        choices=list(COLOR_PALETTE.keys()) + ['rainbow'],
        help='Rain color (default: green)'
    )

    parser.add_argument(
        '-s', '--speed',
        type=int,
        default=5,
        choices=range(1, 11),
        metavar='1-10',
        help='Animation speed, 1=slow, 10=fast (default: 5)'
    )

    parser.add_argument(
        '-d', '--density',
        type=int,
        default=7,
        choices=range(1, 11),
        metavar='1-10',
        help='Rain density, 1=sparse, 10=very dense (default: 7)'
    )

    parser.add_argument(
        '-S', '--screensaver',
        action='store_true',
        help='Screensaver mode - exit on any keypress'
    )

    parser.add_argument(
        '-r', '--rainbow',
        action='store_true',
        help='Rainbow mode - cycling colors'
    )

    return parser.parse_args(argv)


def _main(stdscr, argv):
    """Entry point wrapped by curses."""
    args = parse_args(argv)

    # Handle rainbow flag
    rainbow = args.rainbow or args.color == 'rainbow'
    color = 'green' if rainbow else args.color

    # Create and run the app
    app = App(
        stdscr,
        color=color,
        speed=args.speed,
        density=args.density,
        screensaver=args.screensaver,
        rainbow=rainbow,
    )
    app.run()


def run(argv=None):
    """Parse args, validate the terminal, and run the app inside curses."""
    if argv is None:
        argv = sys.argv[1:]

    # Parse args first to handle --help without needing a TTY
    if '-h' in argv or '--help' in argv:
        parse_args(argv)
        sys.exit(0)

    # Check if we're running in a real terminal
    if not sys.stdout.isatty():
        print("Error: matrix-rain requires a terminal to run.", file=sys.stderr)
        print("Please run this command directly in your terminal.", file=sys.stderr)
        sys.exit(1)

    # Wrap main in curses wrapper for proper terminal handling
    try:
        curses.wrapper(_main, argv)
    except KeyboardInterrupt:
        pass
    except curses.error as e:
        print(f"Terminal error: {e}", file=sys.stderr)
        print("Make sure you're running in a proper terminal.", file=sys.stderr)
        sys.exit(1)
    finally:
        # Ensure terminal is restored
        print("\033[?25h", end='')  # Show cursor
        print("\033[0m", end='')    # Reset colors
