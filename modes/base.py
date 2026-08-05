"""Shared interface every visualizer mode plugin implements.

A mode owns whatever state it needs (columns, node fields, phase...) and
renders through the App's shared helpers (``add_char``, ``get_color_attr``,
``get_contrast_attr``) — it never touches ``curses`` directly.
"""


class Mode:
    name = 'base'

    def reset(self, app):
        """(Re)initialize mode-local state, sized to the current terminal.

        Called once when the app starts (for the initially active mode)
        and again whenever the mode itself needs to treat its cached state
        as stale (e.g. on activation, or after a resize/density change it
        cares about). Not called automatically on every mode switch — see
        ``core.app.App.cycle_mode``.
        """

    def render(self, app):
        """Advance state by one frame and draw it.

        Called once per frame while this mode is active.
        """
