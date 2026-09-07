"""qam command line: run the daemon, install it, inspect it, edit the config."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import APP_ID, OBJECT_PATH, __version__
from .core import config as config_module
from .core.model import ConfigError, Item

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def _colour(text: str, code: str) -> str:
    return f"{code}{text}{RESET}" if sys.stdout.isatty() else text


def _platform():
    from .platform import detect

    return detect()


def _daemon_argv() -> tuple[list[str], str | None]:
    """How systemd should start the daemon, and the source root it needs (if any).

    An installed `qam` script is self-contained; running out of a checkout needs
    the repository on PYTHONPATH, because systemd starts us from elsewhere.
    """
    entry = shutil.which("qam")
    if entry and not entry.endswith(".py"):
        return [entry, "daemon"], None
    root = Path(__file__).resolve().parent.parent
    return [sys.executable, "-m", "qam", "daemon"], str(root)


# ------------------------------------------------------------------- commands
def cmd_daemon(args) -> int:
    from .app import Daemon

    return Daemon().run([sys.argv[0]])


def _activate(action: str) -> int:
    """Ask the running daemon to perform one of its D-Bus actions."""
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gio, GLib

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync(
            APP_ID, OBJECT_PATH, "org.freedesktop.Application", "ActivateAction",
            GLib.Variant("(sava{sv})", (action, [], {})), None,
            Gio.DBusCallFlags.NONE, 2000, None,
        )
        return 0
    except GLib.Error as exc:
        print(f"could not reach the qam daemon: {exc.message}", file=sys.stderr)
        print("start it with `qam daemon` or `systemctl --user start qam`", file=sys.stderr)
        return 1


def cmd_show(args) -> int:
    return _activate("show")


def cmd_toggle(args) -> int:
    return _activate("toggle")


def cmd_install(args) -> int:
    platform = _platform()
    path = config_module.ensure_exists()
    print(f"config    {path}")

    try:
        settings = config_module.load(path).settings
    except ConfigError as exc:
        print(_colour(f"config is unusable: {exc}", RED), file=sys.stderr)
        return 1

    hotkey = args.hotkey or settings.hotkey
    clash = platform.conflicting_binding(hotkey)
    if clash:
        print(_colour(f"warning: {hotkey} is already bound to {clash!r}", RED))
        print("         pick another with --hotkey, or unbind that one first")

    argv, source_root = _daemon_argv()
    print(f"service   {platform.install_service(argv, source_root)}")
    print(f"hotkey    {platform.install_hotkey(hotkey)}")
    print()
    print(f"Press {hotkey.replace('<', '').replace('>', '+')} to open the wheel.")
    print("Undo everything with `qam uninstall`.")
    return 0


def cmd_uninstall(args) -> int:
    platform = _platform()
    print(f"hotkey    {platform.uninstall_hotkey()}")
    print(f"service   {platform.uninstall_service()}")
    print(f"config    left in place at {config_module.config_path()}")
    return 0


def cmd_doctor(args) -> int:
    platform = _platform()
    rows = list(platform.describe())

    path = config_module.config_path()
    try:
        config = config_module.load(path)
        detail = f"{len(config.wheels)} wheel(s), " \
                 f"{sum(len(w.items) for w in config.wheels)} item(s) at {path}"
        rows.append(("config", detail, True))
        for warning in config.warnings:
            rows.append(("config warning", warning, False))
    except ConfigError as exc:
        rows.append(("config", str(exc), False))

    width = max(len(name) for name, _, _ in rows)
    failures = 0
    for name, detail, ok in rows:
        mark = _colour("ok  ", GREEN) if ok else _colour("fail", RED)
        failures += 0 if ok else 1
        print(f"{mark}  {name.ljust(width)}  {_colour(detail, DIM)}")
    return 0 if failures == 0 else 1


def cmd_edit(args) -> int:
    path = config_module.ensure_exists()
    editor_command = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor_command:
        for candidate in ("nano", "vim", "vi"):
            if shutil.which(candidate):
                editor_command = candidate
                break
    if not editor_command:
        print(path)
        return 0
    return subprocess.call([*editor_command.split(), str(path)])


def cmd_add(args) -> int:
    """Append an item to a wheel from the shell - handy for scripting."""
    path = config_module.config_path()
    try:
        config = config_module.load(path)
    except ConfigError as exc:
        print(_colour(str(exc), RED), file=sys.stderr)
        return 1

    index = config.wheel_index(args.wheel) if args.wheel else config.start_index()
    if index is None:
        print(f"no wheel with id {args.wheel!r}", file=sys.stderr)
        return 1

    value = args.value
    if value == "-":
        value = sys.stdin.read().rstrip("\n")
    label = args.label or " ".join(value.split())[:28]
    config.wheels[index].items.append(
        Item(label=label, type=args.type, value=value, icon=args.icon)
    )
    config_module.save(config, path)
    print(f"added {label!r} to wheel {config.wheels[index].id!r}")
    return 0


def cmd_path(args) -> int:
    print(config_module.config_path())
    return 0


# ---------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qam", description="A game-style radial quick access menu."
    )
    parser.add_argument("--version", action="version", version=f"qam {__version__}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("daemon", help="run the resident daemon (what systemd starts)")
    sub.add_parser("show", help="open the wheel now")
    sub.add_parser("toggle", help="open the wheel, or close it if it is up")

    install = sub.add_parser("install", help="install the hotkey and background service")
    install.add_argument("--hotkey", help="override the hotkey, e.g. '<Alt>q'")

    sub.add_parser("uninstall", help="remove the hotkey and background service")
    sub.add_parser("doctor", help="check that everything is wired up")
    sub.add_parser("edit", help="open config.toml in $EDITOR")
    sub.add_parser("path", help="print the path of config.toml")

    add = sub.add_parser("add", help="append an item to a wheel")
    add.add_argument("value", help="the item value, or - to read stdin")
    add.add_argument("--label")
    add.add_argument("--type", default="snippet")
    add.add_argument("--icon")
    add.add_argument("--wheel", help="wheel id (default: the starting wheel)")
    return parser


COMMANDS = {
    "daemon": cmd_daemon,
    "show": cmd_show,
    "toggle": cmd_toggle,
    "install": cmd_install,
    "uninstall": cmd_uninstall,
    "doctor": cmd_doctor,
    "edit": cmd_edit,
    "add": cmd_add,
    "path": cmd_path,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
