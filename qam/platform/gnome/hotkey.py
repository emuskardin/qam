"""Registering the global hotkey as a GNOME custom keybinding.

Wayland gives no application the ability to grab a key globally, so qam asks
GNOME to hold the shortcut for it - the same mechanism the Settings app uses,
which means the user can see and change it there like any other shortcut.
"""

from __future__ import annotations

from gi.repository import Gio

from ... import APP_ID, OBJECT_PATH

MEDIA_KEYS = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_SCHEMA = f"{MEDIA_KEYS}.custom-keybinding"
CUSTOM_BASE = f"/{MEDIA_KEYS.replace('.', '/')}/custom-keybindings/"
BINDING_NAME = "qam quick access menu"


def activation_command() -> str:
    """The command GNOME runs when the hotkey is pressed.

    It toggles rather than shows, so the same key that opens the wheel closes
    it again - pressing it twice must never leave the overlay stuck open.

    Deliberately `gdbus` and not a `qam` client: gdbus is a small C binary that
    hands the request to the resident daemon in a few milliseconds, where
    spawning a Python interpreter per keypress would be felt as lag every time.
    """
    return (
        f"gdbus call --session --dest {APP_ID} --object-path {OBJECT_PATH} "
        f"--method org.freedesktop.Application.ActivateAction toggle [] {{}}"
    )


def _registry() -> tuple[Gio.Settings, list[str]]:
    settings = Gio.Settings.new(MEDIA_KEYS)
    return settings, list(settings.get_strv("custom-keybindings"))


def _entry(path: str) -> Gio.Settings:
    return Gio.Settings.new_with_path(CUSTOM_SCHEMA, path)


def find() -> str | None:
    """dconf path of qam's own keybinding, if it is installed."""
    _, paths = _registry()
    for path in paths:
        if _entry(path).get_string("name") == BINDING_NAME:
            return path
    return None


def conflicting(hotkey: str) -> str | None:
    """Name of an unrelated custom keybinding already using this hotkey."""
    _, paths = _registry()
    for path in paths:
        entry = _entry(path)
        if entry.get_string("name") == BINDING_NAME:
            continue
        if entry.get_string("binding") == hotkey:
            return entry.get_string("name") or path
    return None


def install(hotkey: str) -> str:
    settings, paths = _registry()
    path = find()
    if path is None:
        index = 0
        while f"{CUSTOM_BASE}custom{index}/" in paths:
            index += 1
        path = f"{CUSTOM_BASE}custom{index}/"
        paths.append(path)
        settings.set_strv("custom-keybindings", paths)
    entry = _entry(path)
    entry.set_string("name", BINDING_NAME)
    entry.set_string("command", activation_command())
    entry.set_string("binding", hotkey)
    Gio.Settings.sync()
    return f"bound {hotkey} ({path})"


def uninstall() -> str:
    settings, paths = _registry()
    path = find()
    if path is None:
        return "no qam keybinding was installed"
    entry = _entry(path)
    for key in ("name", "command", "binding"):
        entry.reset(key)
    settings.set_strv("custom-keybindings", [p for p in paths if p != path])
    Gio.Settings.sync()
    return f"removed keybinding ({path})"


def status() -> tuple[bool, str]:
    path = find()
    if path is None:
        return False, "not registered - run `qam install`"
    return True, f"{_entry(path).get_string('binding')} -> gdbus activation"
