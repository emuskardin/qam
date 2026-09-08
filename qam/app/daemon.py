"""The resident application: owns the config, the overlay and the D-Bus action."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib  # noqa: E402

from .. import APP_ID  # noqa: E402
from ..core import actions, config as config_module  # noqa: E402
from ..core.model import Config, ConfigError, Item  # noqa: E402
from ..platform import detect  # noqa: E402
from ..ui import theme  # noqa: E402
from ..ui.editor import install_css as install_editor_css  # noqa: E402
from ..ui.overlay import Overlay  # noqa: E402
from .editing import EditSession  # noqa: E402


class Daemon(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.platform = detect()
        self.store: config_module.ConfigStore | None = None
        self.window: Overlay | None = None
        self.editing = EditSession(self)
        self._accent = theme.DEFAULT_ACCENT

        show = Gio.SimpleAction.new("show", None)
        show.connect("activate", lambda *_: self.show_wheel())
        self.add_action(show)

        toggle = Gio.SimpleAction.new("toggle", None)
        toggle.connect("activate", lambda *_: self.toggle_wheel())
        self.add_action(toggle)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)

    # ------------------------------------------------------------------ config
    @property
    def config(self) -> Config:
        return self.store.config if self.store else Config()

    @property
    def editor_open(self) -> bool:
        return self.editing.open

    @property
    def accent(self):
        return self._accent

    def _resolve_accent(self):
        override = self.config.settings.accent
        if override:
            try:
                self._accent = theme.rgba(override)
                return
            except ValueError:
                pass
        # Follow the user's GNOME accent colour so qam looks native by default.
        try:
            style = Adw.StyleManager.get_default()
            colour = style.get_accent_color_rgba()
            self._accent = (colour.red, colour.green, colour.blue, 1.0)
        except (AttributeError, TypeError):
            self._accent = theme.DEFAULT_ACCENT

    def _on_config_changed(self, _config):
        self._resolve_accent()
        if self.window:
            self.window.refresh()

    def _sync_theme(self, style, *_args):
        """Keep both GTK widgets and our custom snapshot drawing in sync."""
        theme.set_dark(style.get_dark())
        if self.window:
            self.window.refresh()

    # ----------------------------------------------------------------- startup
    def do_startup(self):
        Adw.Application.do_startup(self)
        self.hold()                       # stay resident with no window on screen
        install_editor_css()
        try:
            config_module.ensure_exists()
            self.store = config_module.ConfigStore()
        except (ConfigError, OSError) as exc:
            self.platform.notify("qam could not start", str(exc))
            raise SystemExit(1) from exc
        self.store.watch(self._on_config_changed)
        self._resolve_accent()
        style = Adw.StyleManager.get_default()
        style.set_color_scheme(Adw.ColorScheme.DEFAULT)
        self._sync_theme(style)
        style.connect("notify::dark", self._sync_theme)
        self.window = Overlay(self, self)

    def do_activate(self):
        # Plain activation (no action) also opens the wheel, so `qam show`
        # works even before the keybinding is installed.
        self.show_wheel()

    # ------------------------------------------------------------------- wheel
    def show_wheel(self, wheel_id: str | None = None):
        if self.window:
            self.window.open_wheel(wheel_id)

    def toggle_wheel(self):
        """What the hotkey calls: open the wheel, or close it if it is up."""
        if self.window and self.window.is_open:
            self.close_wheel()
        else:
            self.show_wheel()

    def close_wheel(self):
        # Drop the editor first: it is a real widget over the overlay and would
        # otherwise linger on a surface that is fading out.
        self.editing.close()
        if self.window:
            self.window.close_wheel()

    # ----------------------------------------------------- overlay callbacks
    def activate(self, item: Item):
        outcome = actions.execute(item, self.platform)
        if outcome.switch_to:
            self.window.switch_to(outcome.switch_to)
            return
        if outcome.error:
            self.window.show_toast(outcome.message, error=True)
            self.window.show_flash(outcome.message, outcome.detail, error=True)
            self.platform.notify(outcome.message, outcome.detail)
            return
        # Confirm the pick in the wheel, briefly, then get out of the way: the
        # point of the wheel is to hand you back to whatever you were doing.
        self.window.show_toast(outcome.toast or outcome.message)
        self.window.show_flash(outcome.message, outcome.detail)
        GLib.timeout_add(int(theme.TOAST_MS), self._close_after_action)
        if self.config.settings.notify and item.type == "snippet":
            self.platform.notify(f"{outcome.message}: {item.label}", outcome.detail)

    def _close_after_action(self):
        self.close_wheel()
        return GLib.SOURCE_REMOVE

    def edit_item(self, wheel_index: int, item_index: int | None):
        self.editing.edit(wheel_index, item_index)

    def delete_item(self, wheel_index: int, item_index: int):
        self.editing.delete(wheel_index, item_index)
