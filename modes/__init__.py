"""Visualizer mode plugins.

Each mode module implements the ``modes.base.Mode`` interface: ``reset(app)``
and ``render(app)``. ``core.app.App`` looks modes up by name through
``MODE_CLASSES``/``MODE_ORDER`` — adding a mode is registering it here, not
editing the orchestrator.
"""

from .koi import KoiMode
from .network import NetworkMode
from .pulse import PulseMode
from .rain import RainMode
from .scanner import ScannerMode  # noqa: F401 — kept for reuse, not registered below (see modes/scanner.py)

# 'm' cycles through these, in this order. Matches the pre-split behavior
# exactly for the first three (rain -> pulse -> network), then koi -> rain...
MODE_ORDER = ['rain', 'pulse', 'network', 'koi']

MODE_CLASSES = {
    'rain': RainMode,
    'pulse': PulseMode,
    'network': NetworkMode,
    'koi': KoiMode,
}
