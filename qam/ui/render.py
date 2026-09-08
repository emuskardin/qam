"""Small helpers over GTK's snapshot API.

qam draws with Gsk rather than Cairo so it needs no python3-gi-cairo and no
system packages beyond the GTK that GNOME already ships - and it gets the
GPU-accelerated path for free.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gsk", "4.0")
from gi.repository import Gdk, Gio, GLib, Graphene, Gsk, Gtk, Pango  # noqa: E402

from . import geometry, theme  # noqa: E402

# How finely arcs are approximated. 3 degrees is well under a pixel of error at
# the radii we draw and keeps the path node small.
ARC_STEP = math.radians(3.0)


def rgba(colour: theme.RGBA) -> Gdk.RGBA:
    value = Gdk.RGBA()
    value.red, value.green, value.blue, value.alpha = colour
    return value


def point(x: float, y: float) -> Graphene.Point:
    return Graphene.Point().init(x, y)


def rect(x: float, y: float, width: float, height: float) -> Graphene.Rect:
    return Graphene.Rect().init(x, y, width, height)


def _arc_points(cx, cy, radius, start, end, reverse=False):
    """Sample a wheel-angle arc into screen-space points."""
    sweep = abs(end - start)
    steps = max(2, int(sweep / ARC_STEP) + 1)
    for index in range(steps + 1):
        fraction = index / steps
        angle = end - sweep * fraction if reverse else start + sweep * fraction
        yield cx + math.sin(angle) * radius, cy - math.cos(angle) * radius


def sector_path(cx, cy, index, count, inner, outer, gap=theme.SECTOR_GAP) -> Gsk.Path:
    """A donut-wedge with a constant-width gap at the hub and rim."""
    outer_start, outer_end = geometry.sector_bounds_for_radius(
        index, count, outer, gap
    )
    inner_start, inner_end = geometry.sector_bounds_for_radius(
        index, count, inner, gap
    )
    builder = Gsk.PathBuilder.new()
    outer_points = list(_arc_points(cx, cy, outer, outer_start, outer_end))
    builder.move_to(*outer_points[0])
    for x, y in outer_points[1:]:
        builder.line_to(x, y)
    for x, y in _arc_points(cx, cy, inner, inner_start, inner_end, reverse=True):
        builder.line_to(x, y)
    builder.close()
    return builder.to_path()


def rounded_rect_path(x, y, width, height, radius) -> Gsk.Path:
    shape = Gsk.RoundedRect()
    shape.init_from_rect(rect(x, y, width, height), radius)
    builder = Gsk.PathBuilder.new()
    builder.add_rounded_rect(shape)
    return builder.to_path()


def ring_path(cx, cy, radius) -> Gsk.Path:
    builder = Gsk.PathBuilder.new()
    builder.add_circle(point(cx, cy), radius)
    return builder.to_path()


def fill(snapshot, path: Gsk.Path, colour: theme.RGBA):
    snapshot.append_fill(path, Gsk.FillRule.WINDING, rgba(colour))


def stroke(snapshot, path: Gsk.Path, colour: theme.RGBA, width: float):
    snapshot.append_stroke(path, Gsk.Stroke.new(width), rgba(colour))


def radial_shadow(snapshot, cx, cy, radius, spread, colour: theme.RGBA):
    """A soft ring of shadow just outside `radius`, lifting the wheel off the desktop."""
    outer = radius + spread
    inner_stop = Gsk.ColorStop()
    inner_stop.offset = 0.0
    inner_stop.color = rgba(colour)
    edge_stop = Gsk.ColorStop()
    edge_stop.offset = radius / outer
    edge_stop.color = rgba(colour)
    fade_stop = Gsk.ColorStop()
    fade_stop.offset = 1.0
    fade_stop.color = rgba(theme.with_alpha(colour, 0.0))
    snapshot.append_radial_gradient(
        rect(cx - outer, cy - outer, outer * 2, outer * 2),
        point(cx, cy), 1.0, 1.0, 0.0, outer,
        [inner_stop, edge_stop, fade_stop],
    )


class TextRenderer:
    """Caches Pango layouts and font descriptions for the labels we redraw at 60fps."""

    def __init__(self, widget: Gtk.Widget):
        self.widget = widget
        self._fonts: dict[tuple[int, bool], Pango.FontDescription] = {}

    def font(self, size: int, bold: bool) -> Pango.FontDescription:
        key = (size, bold)
        if key not in self._fonts:
            description = Pango.FontDescription()
            description.set_family(theme.FONT)
            description.set_size(size * Pango.SCALE)
            if bold:
                description.set_weight(Pango.Weight.BOLD)
            self._fonts[key] = description
        return self._fonts[key]

    def layout(self, text: str, size: int, bold=False, width=0, wrap=False) -> Pango.Layout:
        layout = self.widget.create_pango_layout(text)
        layout.set_font_description(self.font(size, bold))
        if width:
            layout.set_width(width * Pango.SCALE)
            layout.set_alignment(Pango.Alignment.CENTER)
            if wrap:
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            else:
                layout.set_ellipsize(Pango.EllipsizeMode.END)
        return layout

    def measure(self, text: str, size: int, bold=False, width=0) -> tuple[float, float]:
        """Pixel width and height `text` would occupy."""
        if not text:
            return 0.0, 0.0
        extent = self.layout(text, size, bold, width).get_pixel_extents()[1]
        return float(extent.width), float(extent.height)

    def centred(self, snapshot, text, x, y, size, colour, bold=False, width=0, wrap=False) -> float:
        """Draw `text` centred on (x, y). Returns its height."""
        if not text:
            return 0.0
        layout = self.layout(text, size, bold, width, wrap)
        extent = layout.get_pixel_extents()[1]
        snapshot.save()
        snapshot.translate(point(x - extent.width / 2.0 - extent.x,
                                 y - extent.height / 2.0 - extent.y))
        snapshot.append_layout(layout, rgba(colour))
        snapshot.restore()
        return extent.height


@lru_cache(maxsize=64)
def _image_icon(path: str):
    try:
        return Gdk.Texture.new_from_file(Gio.File.new_for_path(path))
    except GLib.Error:
        return None


def draw_icon(snapshot, widget: Gtk.Widget, icon_name: str, x, y, size, colour) -> bool:
    """Paint a symbolic icon centred on (x, y), recoloured to `colour`."""
    path = Path(icon_name).expanduser()
    if path.is_file():
        texture = _image_icon(str(path))
        if texture is None:
            return False
        snapshot.save()
        snapshot.translate(point(x - size / 2.0, y - size / 2.0))
        texture.snapshot(snapshot, size, size)
        snapshot.restore()
        return True
    theme_icons = Gtk.IconTheme.get_for_display(widget.get_display())
    paintable = theme_icons.lookup_icon(
        icon_name, None, size, widget.get_scale_factor(),
        Gtk.TextDirection.NONE, Gtk.IconLookupFlags.FORCE_SYMBOLIC,
    )
    if paintable is None:
        return False
    snapshot.save()
    snapshot.translate(point(x - size / 2.0, y - size / 2.0))
    try:
        paintable.snapshot_symbolic(snapshot, size, size, [rgba(colour)])
    except (TypeError, AttributeError):
        paintable.snapshot(snapshot, size, size)
    snapshot.restore()
    return True
