"""The wheel itself: a transparent fullscreen surface that paints one radial menu.

Why fullscreen when only the wheel is visible: Wayland gives an application no
say over where its windows land and no way to read the global pointer, so the
only way to draw a reliably screen-centred menu and to track the pointer
wherever it goes is to own the whole surface. Everything outside the wheel is
left untouched, so the desktop shows straight through.
"""

from __future__ import annotations

import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import geometry, render, theme  # noqa: E402
from ..core.model import Config, Item, Wheel  # noqa: E402


class WheelView(Gtk.Widget):
    """Draws the current wheel. All state comes from the callable it is given."""

    def __init__(self, get_state):
        super().__init__()
        self._state = get_state
        self.text = render.TextRenderer(self)

    # --------------------------------------------------------------------- draw
    def do_snapshot(self, snapshot):
        state = self._state()
        wheel: Wheel | None = state["wheel"]
        progress = state["progress"]
        if wheel is None or progress <= 0.001:
            return

        cx, cy = self.get_width() / 2.0, self.get_height() / 2.0
        inner = float(state["inner"])
        outer = float(state["outer"])

        # The whole wheel pops into place and fades, scaled about its centre.
        scale = 0.86 + 0.14 * theme.ease_out_back(progress) if progress < 1.0 else 1.0
        snapshot.push_opacity(theme.clamp(progress))
        snapshot.save()
        snapshot.translate(render.point(cx, cy))
        snapshot.scale(scale, scale)
        snapshot.translate(render.point(-cx, -cy))

        if wheel.items:
            render.radial_shadow(snapshot, cx, cy, outer, theme.SHADOW_SPREAD, theme.SHADOW)
            for index, item in enumerate(wheel.items):
                self._sector(snapshot, cx, cy, index, item, inner, outer, state)
        else:
            self._empty_ring(snapshot, cx, cy, inner, outer)

        self._hub(snapshot, cx, cy, inner, wheel, state)
        self._footer(snapshot, cx, cy, outer, state)

        snapshot.restore()
        snapshot.pop()

    def _sector(self, snapshot, cx, cy, index, item: Item, inner, outer, state):
        count = len(state["wheel"].items)
        accent = state["accent"]
        heat = state["heat"].get(index, 0.0)          # 0 idle .. 1 fully hovered
        grown = outer + theme.HOVER_LIFT * heat
        fill = theme.mix(
            theme.SECTOR_IDLE, theme.with_alpha(accent, 0.96),
            heat * theme.SECTOR_HOVER_MIX,
        )

        if heat > 0.01:                                # accent glow behind the slice
            glow = render.sector_path(cx, cy, index, count, inner - 4, grown + 12 * heat)
            render.fill(snapshot, glow, theme.with_alpha(accent, 0.20 * heat))

        path = render.sector_path(cx, cy, index, count, inner, grown)
        render.fill(snapshot, path, fill)
        render.stroke(
            snapshot, path,
            theme.mix(theme.SECTOR_EDGE, theme.SECTOR_EDGE_ACTIVE, heat),
            1.0 + heat,
        )

        dx, dy = geometry.sector_centroid(index, count, inner, grown)
        ix, iy = cx + dx, cy + dy
        colour = theme.mix(theme.TEXT_DIM, theme.TEXT_ON_ACCENT, max(heat, 0.40))

        icon_drawn = render.draw_icon(
            snapshot, self, item.icon_name, ix, iy - 13, theme.ICON_SIZE, colour
        )
        arc = geometry.sector_span(count) * (inner + grown) / 2.0
        self.text.centred(
            snapshot, item.label, ix, iy + (15 if icon_drawn else 0),
            theme.LABEL_SIZE, colour, bold=heat > 0.5,
            width=int(min(max(arc * 0.8, 72.0), 160.0)),
        )

        # Slices carry their 1-9 shortcut so the keyboard route is discoverable.
        # It sits just outside the hub, clear of the icon and label above it.
        if index < 9:
            bx, by = geometry.sector_centroid(index, count, inner + 8, inner + 30)
            self.text.centred(
                snapshot, str(index + 1), cx + bx, cy + by, theme.BADGE_SIZE,
                theme.with_alpha(
                    theme.TEXT_ON_ACCENT if heat > 0.5 else theme.TEXT,
                    0.28 + 0.55 * heat,
                ),
                bold=heat > 0.5,
            )

    def _empty_ring(self, snapshot, cx, cy, inner, outer):
        count = 6
        for index in range(count):
            path = render.sector_path(cx, cy, index, count, inner, outer)
            render.stroke(snapshot, path, theme.with_alpha(theme.TEXT, 0.12), 1.5)

    def _hub(self, snapshot, cx, cy, inner, wheel: Wheel, state):
        disc = render.ring_path(cx, cy, inner - 6)
        render.fill(snapshot, disc, theme.HUB_FILL)
        render.stroke(snapshot, disc, theme.HUB_EDGE, 1.0)

        width = int((inner - 22) * 2)
        hovered = state["hovered"]

        if state["editing"] and not state["flash"]:
            self.text.centred(snapshot, "EDIT MODE", cx, cy - 16, theme.HUB_HINT_SIZE,
                              state["accent"], bold=True, width=width)
            self.text.centred(snapshot, state["edit_hint"], cx, cy + 8,
                              theme.HUB_HINT_SIZE, theme.TEXT_DIM, width=width)
        elif state["flash"]:
            message, detail, error = state["flash"]
            self.text.centred(snapshot, message, cx, cy - 14, theme.HUB_TITLE_SIZE,
                              theme.WARNING if error else theme.TEXT, bold=True, width=width)
            self.text.centred(snapshot, detail, cx, cy + 12, theme.HUB_HINT_SIZE,
                              theme.TEXT_DIM, width=width)
        elif hovered is not None and 0 <= hovered < len(wheel.items):
            item = wheel.items[hovered]
            self.text.centred(snapshot, item.label, cx, cy - 18, theme.HUB_TITLE_SIZE,
                              theme.TEXT, bold=True, width=width)
            preview = item.value.removesuffix(".desktop") if item.type == "app" else item.value
            self.text.centred(snapshot, " ".join(preview.split()), cx, cy + 4,
                              theme.HUB_HINT_SIZE, theme.TEXT_DIM, width=width)
            self.text.centred(snapshot, item.hint.upper(), cx, cy + 26, 8,
                              theme.with_alpha(theme.TEXT_DIM, 0.65), width=width)
        else:
            self.text.centred(snapshot, wheel.title, cx, cy - 8, theme.HUB_TITLE_SIZE,
                              theme.TEXT, bold=True, width=width)
            hint = "point at a slice" if wheel.items else "press E, then N to add"
            self.text.centred(snapshot, hint, cx, cy + 14, theme.HUB_HINT_SIZE,
                              theme.TEXT_DIM, width=width)

    def _footer(self, snapshot, cx, cy, outer, state):
        """The caption under the wheel: wheel dots, warnings and key hints.

        Unlike everything else, this sits straight on the desktop rather than on
        the wheel, so each row carries its own pill - over a light wallpaper the
        bare text is unreadable.
        """
        y = cy + outer + 30
        for kind, payload, width, height in self._footer_rows(state):
            plate_width = width + theme.PLATE_PAD_X * 2
            plate_height = height + theme.PLATE_PAD_Y * 2
            plate = render.rounded_rect_path(
                cx - plate_width / 2.0, y, plate_width, plate_height,
                plate_height / 2.0,
            )
            render.fill(snapshot, plate, theme.PLATE)
            render.stroke(snapshot, plate, theme.PLATE_EDGE, 1.0)

            middle = y + plate_height / 2.0
            if kind == "dots":
                self._draw_dots(snapshot, cx, middle, state)
            else:
                text, size, colour = payload
                self.text.centred(snapshot, text, cx, middle, size, colour)
            y += plate_height + theme.PLATE_GAP

    def _footer_rows(self, state):
        """(kind, payload, width, height) for each line of the caption."""
        rows = []
        wheels = state["wheels"]
        if len(wheels) > 1:
            rows.append(("dots", None, self._dots_width(wheels), 10.0))
            title = state["wheel"].title
            width, height = self.text.measure(title, theme.FOOTER_SIZE)
            rows.append(("text", (title, theme.FOOTER_SIZE, theme.TEXT), width, height))

        for warning in state["warnings"][:2]:
            width, height = self.text.measure(warning, theme.FOOTER_SIZE)
            rows.append(("text", (warning, theme.FOOTER_SIZE, theme.WARNING), width, height))

        hints = state["footer"]
        width, height = self.text.measure(hints, theme.FOOTER_SIZE)
        rows.append((
            "text", (hints, theme.FOOTER_SIZE, theme.with_alpha(theme.TEXT, 0.72)),
            width, height,
        ))
        return rows

    @staticmethod
    def _dots_width(wheels) -> float:
        return theme.DOT_SPACING * max(len(wheels) - 1, 0) + theme.DOT_RADIUS * 2

    def _draw_dots(self, snapshot, cx, y, state):
        wheels = state["wheels"]
        start = cx - theme.DOT_SPACING * (len(wheels) - 1) / 2.0
        for index in range(len(wheels)):
            active = index == state["wheel_index"]
            dot = render.ring_path(
                start + index * theme.DOT_SPACING, y,
                theme.DOT_RADIUS if active else theme.DOT_RADIUS - 1.0,
            )
            render.fill(
                snapshot, dot,
                state["accent"] if active else theme.with_alpha(theme.TEXT, 0.40),
            )


class Overlay(Gtk.ApplicationWindow):
    """The window that hosts the wheel and owns all of its input handling."""

    NORMAL_FOOTER = "1-9 pick  ·  Tab wheel  ·  E edit  ·  Esc close"
    EDIT_FOOTER = "click or 1-9 to edit  ·  N new  ·  Del remove  ·  Esc done"

    def __init__(self, application, controller):
        super().__init__(application=application)
        self.controller = controller
        self.set_decorated(False)
        self.set_title("qam")

        self.wheel_index = 0
        self.hovered: int | None = None
        self.heat: dict[int, float] = {}
        self.progress = 0.0
        self.target = 0.0
        self.flash: tuple[str, str, bool] | None = None
        self.editing = False
        self.edit_hint = ""
        self._alt_armed = False
        self._pointer_seen = False
        self._tick_id = None
        self._last_frame = 0.0
        self._flash_source = None

        self.view = WheelView(self._snapshot_state)
        self.view.set_hexpand(True)
        self.view.set_vexpand(True)
        self.overlay = Gtk.Overlay()
        self.overlay.set_child(self.view)
        self.set_child(self.overlay)

        self._install_controllers()
        self._make_transparent()

    # ---------------------------------------------------------------- plumbing
    def _make_transparent(self):
        provider = Gtk.CssProvider()
        provider.load_from_string(
            "window.qam, window.qam > * { background: none; background-color: transparent; }"
        )
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.add_css_class("qam")

    def _install_controllers(self):
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key_pressed)
        keys.connect("key-released", self._on_key_released)
        self.add_controller(keys)

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        self.add_controller(motion)

        click = Gtk.GestureClick()
        click.set_button(0)
        click.connect("pressed", self._on_click)
        self.add_controller(click)

        scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.BOTH_AXES)
        scroll.connect("scroll", self._on_scroll)
        self.add_controller(scroll)

    # ------------------------------------------------------------------- state
    @property
    def config(self) -> Config:
        return self.controller.config

    @property
    def wheels(self) -> list[Wheel]:
        return self.config.wheels

    @property
    def wheel(self) -> Wheel | None:
        if not self.wheels:
            return None
        self.wheel_index = min(self.wheel_index, len(self.wheels) - 1)
        return self.wheels[self.wheel_index]

    def _snapshot_state(self) -> dict:
        return {
            "wheel": self.wheel,
            "wheels": self.wheels,
            "wheel_index": self.wheel_index,
            "hovered": self.hovered,
            "heat": self.heat,
            "progress": self.progress,
            "accent": self.controller.accent,
            "inner": self.config.settings.inner_radius,
            "outer": self.config.settings.outer_radius,
            "flash": self.flash,
            "editing": self.editing,
            "edit_hint": self.edit_hint,
            "warnings": self.config.warnings,
            "footer": self.EDIT_FOOTER if self.editing else self.NORMAL_FOOTER,
        }

    # ------------------------------------------------------------- show / hide
    @property
    def is_open(self) -> bool:
        """On screen and not already on its way out."""
        return self.get_visible() and self.target > 0.0

    def open_wheel(self, wheel_id: str | None = None):
        already_open = self.is_open
        if wheel_id is not None:
            found = self.config.wheel_index(wheel_id)
            if found is not None:
                self.wheel_index = found
        elif not already_open:
            self.wheel_index = self.config.start_index()

        if not already_open:
            self.hovered = None
            self.heat.clear()
            self.flash = None
            self.editing = False
            self._pointer_seen = False
            self.progress = 0.0
            # If Alt is still held when the wheel appears, letting go of it
            # picks the hovered slice - the hold-to-select feel of a weapon wheel.
            self._alt_armed = True
            self._apply_surface_mode()
            self.set_visible(True)
            self.present()
        self.target = 1.0
        self._start_ticking()

    def _apply_surface_mode(self):
        """Put the surface on screen the way this compositor wants.

        The overlay has to cover the screen: Wayland gives no control over
        window placement, so owning a screen-sized surface is the only way to
        centre the wheel reliably and keep following the pointer. It is
        *maximized* rather than fullscreen because GNOME composites nothing
        behind a fullscreen surface - a transparent one would show black
        instead of the desktop.
        """
        mode = self.config.settings.overlay_mode
        if mode == "fullscreen":
            self.fullscreen()
        elif mode == "window":
            self.unmaximize()
            span = int((self.config.settings.outer_radius + 140) * 2)
            self.set_default_size(span, span)
        else:
            self.unfullscreen()
            self.maximize()

    def close_wheel(self, *_):
        if self.target == 0.0 and not self.get_visible():
            return
        self.target = 0.0
        self._alt_armed = False
        self.editing = False
        self._start_ticking()

    def _start_ticking(self):
        self._last_frame = time.monotonic()
        if self._tick_id is None:
            self._tick_id = self.add_tick_callback(self._tick)

    def _tick(self, _widget, _clock):
        now = time.monotonic()
        elapsed = min((now - self._last_frame) * 1000.0, 64.0)
        self._last_frame = now

        duration = theme.OPEN_MS if self.target > self.progress else theme.CLOSE_MS
        delta = elapsed / duration
        if self.target > self.progress:
            self.progress = min(self.target, self.progress + delta)
        else:
            self.progress = max(self.target, self.progress - delta)

        settled = True
        indices = set(self.heat)
        if self.hovered is not None:
            indices.add(self.hovered)
        for index in indices:
            goal = 1.0 if index == self.hovered else 0.0
            current = self.heat.get(index, 0.0)
            move = elapsed / theme.HOVER_MS
            current = min(goal, current + move) if goal > current else max(goal, current - move)
            if current <= 0.001 and goal == 0.0:
                self.heat.pop(index, None)
            else:
                self.heat[index] = current
                settled = settled and abs(current - goal) < 0.001

        self.view.queue_draw()

        if self.progress == self.target and settled:
            self._tick_id = None
            if self.progress == 0.0:
                self.set_visible(False)
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    # ------------------------------------------------------------------- input
    def _hit(self, x: float, y: float) -> int | None:
        wheel = self.wheel
        if wheel is None or not wheel.items:
            return None
        return geometry.hit_test(
            x - self.get_width() / 2.0, y - self.get_height() / 2.0,
            len(wheel.items), self.config.settings.inner_radius,
        )

    def _set_hovered(self, index: int | None):
        if index != self.hovered:
            self.hovered = index
            self.flash = None
            self._start_ticking()

    def _on_motion(self, _controller, x, y):
        if self.controller.editor_open:
            return
        self._pointer_seen = True
        self._set_hovered(self._hit(x, y))

    def _on_scroll(self, _controller, dx, dy):
        wheel = self.wheel
        if wheel and wheel.items:
            self._set_hovered(
                geometry.step(self.hovered, 1 if (dy or dx) > 0 else -1, len(wheel.items))
            )
        return True

    def _on_click(self, gesture, _n_press, x, y):
        if self.controller.editor_open:
            return
        index = self._hit(x, y)
        if index is None:                       # the dead zone and the void cancel
            self.close_wheel()
            return
        self._set_hovered(index)
        if gesture.get_current_button() == Gdk.BUTTON_SECONDARY or self.editing:
            self.controller.edit_item(self.wheel_index, index)
        else:
            self.activate_index(index)

    def _on_key_pressed(self, _controller, keyval, _code, state):
        if self.controller.editor_open:
            return False
        wheel = self.wheel
        count = len(wheel.items) if wheel else 0

        if keyval == Gdk.KEY_Escape:
            self.set_editing(False) if self.editing else self.close_wheel()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and self.hovered is not None:
            if self.editing:
                self.controller.edit_item(self.wheel_index, self.hovered)
            else:
                self.activate_index(self.hovered)
            return True
        if Gdk.KEY_1 <= keyval <= Gdk.KEY_9:
            index = keyval - Gdk.KEY_1
            if index < count:
                self._set_hovered(index)
                if self.editing:
                    self.controller.edit_item(self.wheel_index, index)
                else:
                    self.activate_index(index)
            return True
        if keyval in (Gdk.KEY_Left, Gdk.KEY_Up) and count:
            self._set_hovered(geometry.step(self.hovered, -1, count))
            return True
        if keyval in (Gdk.KEY_Right, Gdk.KEY_Down) and count:
            self._set_hovered(geometry.step(self.hovered, 1, count))
            return True
        if keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            back = keyval == Gdk.KEY_ISO_Left_Tab or bool(state & Gdk.ModifierType.SHIFT_MASK)
            self.cycle_wheel(-1 if back else 1)
            return True
        if keyval in (Gdk.KEY_e, Gdk.KEY_E):
            self.set_editing(not self.editing)
            return True
        if keyval in (Gdk.KEY_n, Gdk.KEY_N) and self.editing:
            self.controller.edit_item(self.wheel_index, None)
            return True
        if keyval in (Gdk.KEY_Delete, Gdk.KEY_BackSpace) and self.editing:
            if self.hovered is not None:
                self.controller.delete_item(self.wheel_index, self.hovered)
            return True
        return False

    def _on_key_released(self, _controller, keyval, _code, _state):
        # Hold-to-select: the hotkey press happens before we exist, but its
        # release lands on us, so letting go of Alt commits the hovered slice.
        if keyval in (Gdk.KEY_Alt_L, Gdk.KEY_Alt_R, Gdk.KEY_Meta_L, Gdk.KEY_Meta_R):
            if self._alt_armed and not self.editing and not self.controller.editor_open:
                self._alt_armed = False
                if self.hovered is not None and self._pointer_seen:
                    self.activate_index(self.hovered)
        return False

    # ------------------------------------------------------------------ actions
    def cycle_wheel(self, delta: int):
        if len(self.wheels) < 2:
            return
        self.wheel_index = (self.wheel_index + delta) % len(self.wheels)
        self.hovered = None
        self.heat.clear()
        self.flash = None
        self._start_ticking()

    def switch_to(self, wheel_id: str):
        found = self.config.wheel_index(wheel_id)
        if found is None:
            self.show_flash("No such wheel", wheel_id, error=True)
            return
        self.wheel_index = found
        self.hovered = None
        self.heat.clear()
        self._alt_armed = False        # do not let the same Alt release fire twice
        self._start_ticking()

    def set_editing(self, editing: bool, hint: str = ""):
        self.editing = editing
        self._alt_armed = False
        self.edit_hint = hint or ("pick a slice, or N for a new one" if editing else "")
        self.flash = None
        self.view.queue_draw()

    def show_flash(self, message: str, detail: str = "", error: bool = False):
        self.flash = (message, detail, error)
        self.view.queue_draw()
        if self._flash_source:
            GLib.source_remove(self._flash_source)
        self._flash_source = GLib.timeout_add(
            1800 if error else 900, self._clear_flash
        )

    def _clear_flash(self):
        self._flash_source = None
        self.flash = None
        self.view.queue_draw()
        return GLib.SOURCE_REMOVE

    def activate_index(self, index: int):
        wheel = self.wheel
        if wheel is None or index >= len(wheel.items):
            return
        self.controller.activate(wheel.items[index])

    def refresh(self):
        """Called when the config changed underneath us."""
        self.wheel_index = min(self.wheel_index, max(len(self.wheels) - 1, 0))
        wheel = self.wheel
        if wheel and self.hovered is not None and self.hovered >= len(wheel.items):
            self.hovered = None
        self.view.queue_draw()
