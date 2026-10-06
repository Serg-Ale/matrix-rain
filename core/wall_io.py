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

from . import color as color_engine
from . import wall
from .app import App
from .screen import Screen

FRAME_DELAY = 0.03          # same ~33 FPS pacing as App.run
SEND_TIMEOUT = 0.25         # a client that can't take a frame for this long is dropped (the host
                            # blocks on it meanwhile, so keep it short)
_QUIT_KEYS = (ord('q'), ord('Q'), 27)


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
    def __init__(self, conn, width=0, height=0):
        self.conn = conn        # None for the host's own terminal
        self.width = width
        self.height = height    # width == 0: hasn't reported its size yet


def run_host(stdscr, listener, args):
    curses.curs_set(0)
    stdscr.nodelay(True)
    height, width = stdscr.getmaxyx()
    local = _Tile(None, width, height)
    tiles = [local]
    canvas = (height, width)
    key_queue = _WallInput()

    app = App(key_queue, color=args.color, mode=args.mode, speed=args.speed,
              density=args.density, rainbow=args.rainbow,
              canvas_size=lambda: canvas)
    local_screen = Screen(height, width)

    def drop(tile):
        tile.conn.close()
        tiles.remove(tile)

    try:
        while True:
            frame_start = time.time()

            # Local keys and size.
            key = stdscr.getch()
            while key != -1:
                if key != curses.KEY_RESIZE:
                    key_queue.keys.append(key)
                key = stdscr.getch()
            local.height, local.width = stdscr.getmaxyx()

            # New clients, and what the existing ones say.
            watched = [listener] + [t.conn for t in tiles if t.conn]
            ready, _, _ = select.select(watched, [], [], 0)
            for source in ready:
                if source is listener:
                    tiles.append(_Tile(listener.accept()))
                    continue
                tile = next(t for t in tiles if t.conn is source)
                messages = tile.conn.receive()
                if messages is None:
                    drop(tile)
                    continue
                for message in messages:
                    if message['t'] == 'size':
                        tile.width, tile.height = message['w'], message['h']
                    elif message['t'] == 'key':
                        key_queue.keys.append(message['k'])

            # The canvas follows the tiles that have reported a size.
            sized = [t for t in tiles if t.width > 0 and t.height > 0]
            placements, canvas_height, canvas_width = wall.layout([(t.width, t.height) for t in sized])
            canvas = (canvas_height, canvas_width)

            if app.check_input():
                break
            app.handle_resize()

            app.render_frame()

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
        pass
    finally:
        for tile in tiles:
            if tile.conn:
                tile.conn.close()
        listener.close()
    return 'wall closed'


# --- client -------------------------------------------------------------------

def run_client(stdscr, conn):
    curses.curs_set(0)
    stdscr.nodelay(True)
    truecolor = color_engine.supports_truecolor()
    height, width = stdscr.getmaxyx()
    screen = Screen(height, width)
    sent_size = None

    try:
        while True:
            # Keys go to the host; q/Esc only leave the wall.
            key = stdscr.getch()
            while key != -1:
                if key in _QUIT_KEYS:
                    return 'left the wall'
                if key != curses.KEY_RESIZE:
                    conn.send(wall.key_message(key))
                key = stdscr.getch()

            height, width = stdscr.getmaxyx()
            if (height, width) != sent_size:
                if not conn.send(wall.size_message(width, height)):
                    return 'host closed the wall'
                sent_size = (height, width)

            ready, _, _ = select.select([conn], [], [], 0.01)
            if not ready:
                continue
            messages = conn.receive()
            if messages is None:
                return 'host closed the wall'

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

def run_wall(stdscr, args, transport=None):
    """Join the wall if a host is running, otherwise become the host.
    Returns a short message for the caller to print once curses is closed."""
    transport = transport or UnixTransport()
    for _ in range(40):
        conn = transport.connect()
        if conn:
            return run_client(stdscr, conn)
        try:
            listener = transport.listen()
        except OSError as error:
            if error.errno != errno.EADDRINUSE:
                raise
            # Someone holds the host lock but isn't accepting yet — it's
            # still starting up. Give it a moment, then try joining again.
            time.sleep(0.05)
            continue
        return run_host(stdscr, listener, args)
    raise RuntimeError('could not join or create the wall')
