"""Command-line entry point: argument parsing and the curses bootstrap."""

import curses
import sys

from modes import MODE_ORDER

from .palette import COLOR_PALETTE
from .wall import parse_at


def _at(text):
    """argparse type for --at."""
    import argparse

    try:
        return parse_at(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "expected ROW,COL as non-negative integers (e.g. 0,1), got '{0}'".format(text))


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
  matrix-rain -m network          # Start straight in Network mode
  matrix-rain --rainbow           # Rainbow mode!
  matrix-rain -S                  # Screensaver mode (exit on keypress)
  matrix-rain --wall              # Video wall: run it in 2+ terminals to join them
  matrix-rain --at 1,0            # Wall tile on row 1, column 0 (implies --wall)
  matrix-rain -c green -s 6 -d 9  # Fast, very dense green rain

Colors available: green, red, blue, cyan, magenta, yellow, white, orange, pink, ice, violet
Modes available: {modes}

Press 'q' or Escape to exit (or any key in screensaver mode). Press 'm' to
cycle modes and 'h' for the full live-control panel once it's running.
        '''.format(modes=', '.join(MODE_ORDER))
    )

    parser.add_argument(
        '-c', '--color',
        type=str,
        default='green',
        choices=list(COLOR_PALETTE.keys()),
        help='Rain color (default: green)'
    )

    parser.add_argument(
        '-m', '--mode',
        type=str,
        default=MODE_ORDER[0],
        choices=MODE_ORDER,
        help='Starting visualizer mode (default: {0}) — cycle live with the '
             "'m' key".format(MODE_ORDER[0])
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

    parser.add_argument(
        '--wall',
        action='store_true',
        help='Video wall - join (or start) a wall shared with other terminals '
             'on this machine, so they act as tiles of one big screen'
    )

    parser.add_argument(
        '--at',
        type=_at,
        metavar='ROW,COL',
        help='Where this terminal sits on the video wall grid (row 0 is the '
             'top, column 0 the left); implies --wall. Without it, terminals '
             'queue up left to right in the order they join'
    )

    args = parser.parse_args(argv)
    if args.at is not None:
        args.wall = True
    if args.wall and args.screensaver:
        parser.error('--wall cannot be combined with -S/--screensaver')
    return args


def _main(stdscr, argv):
    """Entry point wrapped by curses."""
    from .wall_io import run_session

    return run_session(stdscr, parse_args(argv))


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
        message = curses.wrapper(_main, argv)
        if message:
            print('wall: ' + message)
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
