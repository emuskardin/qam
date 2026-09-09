"""Carrying an action out on GNOME: clipboard, notifications, launching."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from gi.repository import Gdk, Gio, GLib

from ... import APP_ID

NOTIFICATION_ID = "qam-action"
NOTIFICATION_SECONDS = 3


def set_clipboard(text: str) -> None:
    display = Gdk.Display.get_default()
    if display is None:
        raise RuntimeError("no display available")
    # Both selections: middle-click paste is second nature for terminal work.
    display.get_clipboard().set(text)
    display.get_primary_clipboard().set(text)


def read_clipboard(on_text) -> None:
    """Read the clipboard asynchronously.

    Only works while qam holds keyboard focus, which on Wayland is precisely
    when the wheel is open - so this is called from the editor and nowhere else.
    """
    display = Gdk.Display.get_default()
    if display is None:
        return

    def finished(source, result):
        try:
            text = source.read_text_finish(result)
        except GLib.Error:
            text = None
        if text:
            on_text(text)

    display.get_clipboard().read_text_async(None, finished)


def notify(title: str, body: str = "") -> None:
    application = Gio.Application.get_default()
    if application is None:
        return
    notification = Gio.Notification.new(title)
    if body:
        notification.set_body(body)
    notification.set_priority(Gio.NotificationPriority.LOW)
    # The wheel mark, installed alongside the desktop entry.
    notification.set_icon(Gio.ThemedIcon.new(APP_ID))
    application.send_notification(NOTIFICATION_ID, notification)
    # These are confirmations, not messages worth keeping around.
    GLib.timeout_add_seconds(
        NOTIFICATION_SECONDS,
        lambda: (application.withdraw_notification(NOTIFICATION_ID), False)[1],
    )


def launch_app(desktop_id: str) -> None:
    if not desktop_id.endswith(".desktop"):
        desktop_id += ".desktop"
    info = Gio.DesktopAppInfo.new(desktop_id)
    if info is None:
        raise RuntimeError(f"no such application: {desktop_id}")
    info.launch_uris_as_manager(
        [], None, GLib.SpawnFlags.SEARCH_PATH, None, None, None, None
    )


def open_path(path: str) -> None:
    expanded = Path(os.path.expandvars(os.path.expanduser(path)))
    if not expanded.exists():
        raise RuntimeError(f"path does not exist: {expanded}")
    open_uri(expanded.as_uri())


def open_uri(uri: str) -> None:
    if "://" not in uri:
        uri = f"https://{uri}"
    Gio.AppInfo.launch_default_for_uri(uri, None)


def run_command(command: str, shell: bool = False) -> None:
    argv = ["/bin/sh", "-c", command] if shell else shlex.split(command)
    if not argv:
        raise RuntimeError("empty command")
    # start_new_session detaches the child so it outlives the daemon and never
    # inherits its controlling terminal.
    subprocess.Popen(
        argv,
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
