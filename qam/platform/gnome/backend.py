"""The GNOME implementation of the Platform protocol, assembled from the
hotkey, service and runtime pieces beside it."""

from __future__ import annotations

import os
import shutil

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gio, GLib  # noqa: E402

from ... import APP_ID  # noqa: E402
from . import appicon, hotkey, runtime, service  # noqa: E402


class GnomePlatform:
    name = "linux/gnome"

    # -------------------------------------------------------------- install
    def install_hotkey(self, key: str) -> str:
        return hotkey.install(key)

    def uninstall_hotkey(self) -> str:
        return hotkey.uninstall()

    def conflicting_binding(self, key: str) -> str | None:
        return hotkey.conflicting(key)

    def install_service(self, executable: list[str], source_root: str | None = None) -> str:
        return service.install(executable, source_root)

    def uninstall_service(self) -> str:
        return service.uninstall()

    def install_desktop_entry(self, executable: list[str], source_root: str | None = None) -> str:
        return appicon.install(executable, source_root)

    def uninstall_desktop_entry(self) -> str:
        return appicon.uninstall()

    # -------------------------------------------------------------- runtime
    def set_clipboard(self, text: str) -> None:
        runtime.set_clipboard(text)

    def read_clipboard(self, on_text) -> None:
        runtime.read_clipboard(on_text)

    def notify(self, title: str, body: str = "") -> None:
        runtime.notify(title, body)

    def launch_app(self, desktop_id: str) -> None:
        runtime.launch_app(desktop_id)

    def open_path(self, path: str) -> None:
        runtime.open_path(path)

    def open_uri(self, uri: str) -> None:
        runtime.open_uri(uri)

    def run_command(self, command: str, shell: bool = False) -> None:
        runtime.run_command(command, shell)

    # ---------------------------------------------------------- diagnostics
    def daemon_running(self) -> tuple[bool, str]:
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            reply = bus.call_sync(
                "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                "NameHasOwner", GLib.Variant("(s)", (APP_ID,)),
                GLib.VariantType("(b)"), Gio.DBusCallFlags.NONE, 1000, None,
            )
            owned = reply.unpack()[0]
        except GLib.Error as exc:
            return False, f"session bus unavailable: {exc.message}"
        return owned, f"{APP_ID} {'is claimed' if owned else 'is not running'}"

    def describe(self) -> list[tuple[str, str, bool]]:
        session = os.environ.get("XDG_SESSION_TYPE", "unknown")
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "unknown")
        gdbus = shutil.which("gdbus")
        rows = [
            ("session", f"{desktop} on {session}", session in ("wayland", "x11")),
            ("gdbus", gdbus or "missing - the hotkey cannot reach the daemon", bool(gdbus)),
        ]
        for label, (ok, detail) in (
            ("hotkey", hotkey.status()),
            ("service", service.status()),
            ("icon", appicon.status()),
            ("daemon", self.daemon_running()),
        ):
            rows.append((label, detail, ok))
        return rows
