"""Video wall I/O: the Unix-socket transport and the host/client loops.

All the logic worth unit-testing lives in core/wall.py; this module is the
curses + socket shell around it and is validated by hand (see AGENTS.md).

The transport is deliberately a small surface — ``connect()`` / ``listen()``
returning ``Connection`` objects with ``send`` / ``receive`` — so a TCP
transport can slot in later without touching the loops below.
"""

import curses
import errno
import fcntl
import os
import select
import socket
import time
from collections import namedtuple

from . import color as color_engine
from . import wall
from .app import App
from .screen import Screen

FRAME_DELAY = 0.03          # same ~33 FPS pacing as App.run
SEND_TIMEOUT = 0.25         # a client that can't take a frame for this long is dropped (the host
                            # blocks on it meanwhile, so keep it short)
_QUIT_KEYS = (ord('q'), ord('Q'), 27)
_TOGGLE_KEYS = (ord('j'), ord('J'))
_LAYOUT_KEYS = (ord('l'), ord('L'))
_ARROWS = {curses.KEY_UP: 'up', curses.KEY_DOWN: 'down', curses.KEY_LEFT: 'left', curses.KEY_RIGHT: 'right'}
GUIDE_COLOR = (255, 0, 255)


# --- transport ----------------------------------------------------------------

def socket_path():
    """Per-user socket location: the runtime dir when there is one."""
    runtime = os.environ.get('XDG_RUNTIME_DIR')
    if runtime and os.path.isdir(runtime):
        return os.path.join(runtime, 'matrix-rain-wall.sock')
    return '/tmp/matrix-rain-wall-{0}.sock'.format(os.getuid())


class Connection:
    """One end of a wall link: send messages, receive decoded messages."""

    def __init__(self, sock):
        self._sock = sock
        self._sock.settimeout(SEND_TIMEOUT)
        self._decoder = wall.LineDecoder()

    def fileno(self):
        return self._sock.fileno()

    def send(self, message):
        """False when the peer is gone or too slow."""
        try:
            self._sock.sendall(wall.encode(message))
        except OSError:
            return False
        return True

    def receive(self):
        """Messages that arrived (call after select says readable), or None
        when the peer closed the link."""
        try:
            data = self._sock.recv(1 << 16)
        except OSError:
            return None
        if not data:
            return None
        return self._decoder.feed(data)

    def close(self):
        try:
            self._sock.close()
        except OSError:
            pass


class Listener:
    def __init__(self, sock, path, lock_fd):
        self._sock = sock
        self._path = path
        self._lock_fd = lock_fd

    def fileno(self):
        return self._sock.fileno()

    def accept(self):
        conn, _ = self._sock.accept()
        return Connection(conn)

    def close(self):
        try:
            os.unlink(self._path)
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass
        os.close(self._lock_fd)  # releases the host lock


class UnixTransport:
    def __init__(self, path=None):
        self.path = path or socket_path()

    def connect(self):
        """A Connection to a running host, or None when there isn't one."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self.path)
        except (FileNotFoundError, ConnectionRefusedError):
            sock.close()
            return None
        return Connection(sock)

    def listen(self):
        """Become the host. Being the host means holding an exclusive lock
        on a lock file next to the socket: the kernel drops it when the
        holder dies, so there's never a stale host to clean up after, and
        two terminals starting at once can't both win. Raises
        OSError(EADDRINUSE) when another process holds it. Only the owning
        user can reach the socket."""
        old_umask = os.umask(0o077)
        try:
            lock_fd = os.open(self.path + '.lock', os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                os.close(lock_fd)
                raise OSError(errno.EADDRINUSE, 'another host holds the wall')
            try:
                os.unlink(self.path)  # whatever a dead host left behind
            except FileNotFoundError:
                pass
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.bind(self.path)
                sock.listen(8)
            except OSError:
                sock.close()
                os.close(lock_fd)
                raise
        finally:
            os.umask(old_umask)
        return Listener(sock, self.path, lock_fd)


# --- host ---------------------------------------------------------------------

class _WallInput:
    """What App sees as its curses window while hosting: a queue of keys
    (local and forwarded). Size comes from App's canvas_size instead."""

    def __init__(self):
        self.keys = []

    def getch(self):
        return self.keys.pop(0) if self.keys else -1

    def nodelay(self, flag):
        pass

    def timeout(self, ms):
        pass


class _Tile:
    def __init__(self, conn, width=0, height=0, at=None):
        self.conn = conn        # None for the host's own terminal
        self.width = width
        self.height = height    # width == 0: hasn't reported its size yet
        self.at = at            # (row, col) on the grid, or None: queue by arrival
        self.layout_mode = False  # arrows move this tile instead of tuning speed/density


# What a stretch inside the wall ended with. ``reason`` is ``'left'`` (the
# user pressed J), ``'gone'`` (the wall dissolved under a client) or
# ``'quit'`` (q/Esc/Ctrl+C); ``snapshot`` is the last shared settings seen,
# for the terminal to carry back to standalone; ``message`` is what to
# print when quitting.
WallResult = namedtuple('WallResult', 'reason snapshot message')


def run_host(stdscr, listener, kwargs, at):
    curses.curs_set(0)
    stdscr.nodelay(True)
    height, width = stdscr.getmaxyx()
    local = _Tile(None, width, height, at)
    tiles = [local]
    canvas = (height, width)
    key_queue = _WallInput()

    app = App(key_queue, canvas_size=lambda: canvas, **kwargs)
    app.wall_active = True
    local_screen = Screen(height, width)
    config = wall.snapshot_of(app)

    def drop(tile):
        tile.conn.close()
        tiles.remove(tile)

    def sized_tiles():
        return [t for t in tiles if t.width > 0 and t.height > 0]

    def handle_key(tile, key):
        """Keys from any tile. L toggles that tile's layout mode, in which
        its arrows move it on the grid; everything else reaches the app."""
        if key in _LAYOUT_KEYS:
            tile.layout_mode = not tile.layout_mode
            app.show_status('Layout mode: arrows move this tile, L exits'
                            if tile.layout_mode else 'Layout mode off')
        elif tile.layout_mode and key in _ARROWS and tile in sized_tiles():
            sized = sized_tiles()
            moved = wall.move_position(
                wall.resolve_positions([t.at for t in sized]), sized.index(tile), _ARROWS[key])
            for t, position in zip(sized, moved):
                t.at = position  # from here on every tile's cell is explicit
        else:
            key_queue.keys.append(key)

    def admit(tile, message):
        """First size report of a newcomer: it takes the cell it asked for,
        and whoever sat there steps aside."""
        tile.width, tile.height = message['w'], message['h']
        others = [t for t in sized_tiles() if t is not tile]
        want = tuple(message['at']) if 'at' in message else None
        if want is not None:
            moved = wall.displace(wall.resolve_positions([t.at for t in others]), want)
            if moved:
                others[moved[0]].at = moved[1]
        tile.at = want

    try:
        while True:
            frame_start = time.time()

            # Local keys and size.
            key = stdscr.getch()
            while key != -1:
                if key != curses.KEY_RESIZE:
                    handle_key(local, key)
                key = stdscr.getch()
            local.height, local.width = stdscr.getmaxyx()

            # New clients, and what the existing ones say.
            watched = [listener] + [t.conn for t in tiles if t.conn]
            ready, _, _ = select.select(watched, [], [], 0)
            for source in ready:
                if source is listener:
                    newcomer = _Tile(listener.accept())
                    tiles.append(newcomer)
                    if not newcomer.conn.send(wall.config_message(config)):
                        drop(newcomer)
                    continue
                tile = next(t for t in tiles if t.conn is source)
                messages = tile.conn.receive()
                if messages is None:
                    drop(tile)
                    continue
                for message in messages:
                    if message['t'] == 'size':
                        if tile.width == 0:
                            admit(tile, message)
                        else:
                            # Later reports are resizes; the host owns the cell.
                            tile.width, tile.height = message['w'], message['h']
                    elif message['t'] == 'key':
                        handle_key(tile, message['k'])

            # The canvas follows the tiles that have reported a size.
            sized = sized_tiles()
            positions = wall.resolve_positions([t.at for t in sized])
            placements, canvas_height, canvas_width = wall.layout(
                [(t.width, t.height) for t in sized], positions)
            canvas = (canvas_height, canvas_width)

            if app.check_input():
                break
            app.handle_resize()

            # Keep every client's idea of the shared settings current.
            current = wall.snapshot_of(app)
            if current != config:
                config = current
                for tile in list(tiles):
                    if tile.conn and not tile.conn.send(wall.config_message(config)):
                        drop(tile)

            app.render_frame()
            editing = any(t.layout_mode for t in sized)
            if editing:
                for tile, (x, y) in zip(sized, placements):  # seam guides on every tile
                    for edge_y in range(y, y + tile.height):
                        app.add_char(edge_y, x, '|', (GUIDE_COLOR, False, False))
                        app.add_char(edge_y, x + tile.width - 1, '|', (GUIDE_COLOR, False, False))
            if app.panel_visible or editing:
                for tile, (row, col), (x, y) in zip(sized, positions, placements):
                    label = ' LAYOUT r{0}c{1} ' if tile.layout_mode else ' WALL r{0}c{1} '
                    app.draw_text(y, x, label.format(row, col), reverse=True)

            for tile, (x, y) in zip(sized, placements):
                cells, bgs = app.screen.extract(y, x, tile.height, tile.width)
                if tile.conn is None:
                    if (local_screen.height, local_screen.width) != (tile.height, tile.width):
                        local_screen.resize(tile.height, tile.width)
                    local_screen.load(cells, bgs)
                    local_screen.flush(app.truecolor)
                elif not tile.conn.send(wall.frame_message(cells, bgs)):
                    drop(tile)

            app.frame_count += 1
            time.sleep(max(0.01, FRAME_DELAY - (time.time() - frame_start)))
    except KeyboardInterrupt:
        app.wall_toggle_requested = False
    finally:
        for tile in tiles:
            if tile.conn:
                tile.conn.close()
        listener.close()
    snapshot = wall.snapshot_of(app)
    if app.wall_toggle_requested:
        return WallResult('left', snapshot, None)
    return WallResult('quit', snapshot, 'wall closed')


# --- client -------------------------------------------------------------------

def run_client(stdscr, conn, at=None):
    curses.curs_set(0)
    stdscr.nodelay(True)
    truecolor = color_engine.supports_truecolor()
    height, width = stdscr.getmaxyx()
    screen = Screen(height, width)
    sent_size = None
    config = None

    try:
        while True:
            # Keys go to the host; q/Esc quit, J leaves the wall.
            key = stdscr.getch()
            while key != -1:
                if key in _QUIT_KEYS:
                    return WallResult('quit', config, 'left the wall')
                if key in _TOGGLE_KEYS:
                    return WallResult('left', config, None)
                if key != curses.KEY_RESIZE:
                    conn.send(wall.key_message(key))
                key = stdscr.getch()

            height, width = stdscr.getmaxyx()
            if (height, width) != sent_size:
                if not conn.send(wall.size_message(width, height, at)):
                    return WallResult('gone', config, None)
                sent_size = (height, width)

            ready, _, _ = select.select([conn], [], [], 0.01)
            if not ready:
                continue
            messages = conn.receive()
            if messages is None:
                return WallResult('gone', config, None)

            for message in messages:
                if message['t'] == 'config':
                    config = wall.config_snapshot(message)
            frames = [m for m in messages if m['t'] == 'frame']
            if not frames:
                continue
            try:
                cells, bgs = wall.frame_cells(frames[-1])  # only the newest matters
            except (ValueError, TypeError):
                continue
            if (screen.height, screen.width) != (height, width):
                screen.resize(height, width)
            screen.load(cells, bgs)
            screen.flush(truecolor)
    finally:
        conn.close()


# --- entry --------------------------------------------------------------------

def run_wall(stdscr, kwargs, at=None, transport=None):
    """Join the wall if a host is running, otherwise become the host with
    ``kwargs`` (App's constructor settings) as the wall's settings."""
    transport = transport or UnixTransport()
    for _ in range(40):
        conn = transport.connect()
        if conn:
            return run_client(stdscr, conn, at)
        try:
            listener = transport.listen()
        except OSError as error:
            if error.errno != errno.EADDRINUSE:
                raise
            # Someone holds the host lock but isn't accepting yet — it's
            # still starting up. Give it a moment, then try joining again.
            time.sleep(0.05)
            continue
        return run_host(stdscr, listener, kwargs, at)
    raise RuntimeError('could not join or create the wall')


def run_session(stdscr, args, transport=None):
    """A terminal's whole life: standalone and the wall, back and forth.

    J joins the wall from standalone and leaves it from inside; entering
    adopts the wall's settings (the host's, or — when this terminal starts
    the wall — its own), leaving keeps whatever the wall had last.
    Returns a message to print on exit, or None.
    """
    settings = {key: getattr(args, key) for key in wall.SNAPSHOT_KEYS}
    in_wall = args.wall
    while True:
        if in_wall:
            result = run_wall(stdscr, settings, args.at, transport)
            if result.reason == 'quit':
                return result.message
            if result.snapshot:
                settings = result.snapshot
            in_wall = False
        else:
            app = App(stdscr, screensaver=args.screensaver, **settings)
            app.run()
            if not app.wall_toggle_requested:
                return None
            settings = wall.snapshot_of(app)
            in_wall = True
