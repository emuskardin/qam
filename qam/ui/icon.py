"""The qam mark: the wheel itself, shrunk down to an application icon.

The icon is drawn with the same primitives and the same palette as the menu, so
it follows the wheel's design by construction instead of being a PNG somebody
has to remember to redraw. Labels, badges and hints all fall away - at 32px the
only things that still read are the ring, the gaps and one accented slice.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
from gi.repository import Gdk, Gsk, Gtk  # noqa: E402

from . import render, theme  # noqa: E402

SECTORS = 6
ACTIVE = 1                       # the slice that carries the accent, clockwise from the top

# All as a fraction of the icon's edge, so one drawing serves every size.
PLATE_RADIUS = 0.22
OUTER = 0.41
INNER = 0.17
GAP = 0.030
PLATE: theme.RGBA = theme.rgba("#16181f", 1.0)
SECTOR: theme.RGBA = theme.rgba("#3c4354", 1.0)
HUB: theme.RGBA = theme.rgba("#0e1013", 1.0)


def snapshot_mark(snapshot, size: float, accent: theme.RGBA = theme.DEFAULT_ACCENT):
    """Paint the mark into `snapshot`, filling a `size` x `size` square."""
    centre = size / 2.0
    outer, inner, gap = size * OUTER, size * INNER, size * GAP

    plate = render.rounded_rect_path(0, 0, size, size, size * PLATE_RADIUS)
    render.fill(snapshot, plate, PLATE)

    for index in range(SECTORS):
        active = index == ACTIVE
        # The accent slice stands proud of the ring, the way a hovered one does.
        rim = outer + (size * 0.035 if active else 0.0)
        path = render.sector_path(centre, centre, index, SECTORS, inner, rim, gap)
        render.fill(snapshot, path, accent if active else SECTOR)
        render.stroke(snapshot, path, theme.with_alpha(theme.TEXT, 0.10), size * 0.006)

    hub = render.ring_path(centre, centre, inner - size * 0.02)
    render.fill(snapshot, hub, HUB)
    render.stroke(snapshot, hub, theme.with_alpha(theme.TEXT, 0.14), size * 0.008)


def render_png(path, size: int, accent: theme.RGBA = theme.DEFAULT_ACCENT) -> None:
    """Rasterise the mark to `path`. Needs a display - Gtk.init() must have run."""
    snapshot = Gtk.Snapshot()
    snapshot_mark(snapshot, float(size), accent)
    renderer = Gsk.CairoRenderer()
    renderer.realize_for_display(Gdk.Display.get_default())
    try:
        renderer.render_texture(snapshot.to_node(), None).save_to_png(str(path))
    finally:
        renderer.unrealize()
