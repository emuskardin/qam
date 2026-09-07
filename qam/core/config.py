"""Loading, validating, saving and watching ~/.config/qam/config.toml."""

from __future__ import annotations

import os
import tempfile
import tomllib
from pathlib import Path
from typing import Callable

from . import tomlwrite
from .model import Config, ConfigError, Item, Settings, Wheel


OVERLAY_MODES = ("maximized", "fullscreen", "window")


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "qam"


def config_path() -> Path:
    override = os.environ.get("QAM_CONFIG")
    return Path(override) if override else config_dir() / "config.toml"


EXAMPLE = """\
# qam configuration
#
# Press Alt+Q to open the wheel, flick the mouse towards a slice and release
# Alt to pick it. Number keys 1-9 pick directly, Tab cycles wheels, Esc closes.
# Press E inside the wheel to edit slices without leaving the keyboard.
#
# Item types:
#   snippet  copy the value to the clipboard   (the everyday one)
#   command  run the value
#   app      launch a desktop application, e.g. "org.gnome.Nautilus.desktop"
#   path     open a file or folder
#   uri      open a URL
#   wheel    jump to another wheel by its id

[settings]
hotkey = "<Alt>q"
default_wheel = "main"
notify = true

[[wheel]]
id = "main"
name = "Main"

  [[wheel.item]]
  label = "Pods (all ns)"
  type = "snippet"
  value = "kubectl get pods -A"

  [[wheel.item]]
  label = "Follow logs"
  type = "snippet"
  value = "kubectl logs -f -n $NS $POD"

  [[wheel.item]]
  label = "Contexts"
  type = "snippet"
  value = "kubectl config get-contexts"

  [[wheel.item]]
  label = "Home"
  type = "path"
  value = "~"

  [[wheel.item]]
  label = "Files"
  type = "app"
  value = "org.gnome.Nautilus.desktop"

  [[wheel.item]]
  label = "Dev"
  type = "wheel"
  value = "dev"

[[wheel]]
id = "dev"
name = "Dev"

  [[wheel.item]]
  label = "Git status"
  type = "snippet"
  value = "git status -sb"

  [[wheel.item]]
  label = "Git log"
  type = "snippet"
  value = "git log --oneline --graph --decorate -20"

  [[wheel.item]]
  label = "Prune branches"
  type = "snippet"
  value = "git branch --merged | grep -v '\\\\*' | xargs -r git branch -d"

  [[wheel.item]]
  label = "Main"
  type = "wheel"
  value = "main"
"""


def _as_str(table: dict, key: str, default: str = "") -> str:
    value = table.get(key, default)
    return value if isinstance(value, str) else str(value)


def parse(text: str) -> Config:
    """Turn TOML text into a Config. Raises ConfigError on unusable input."""
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"config is not valid TOML: {exc}") from exc

    warnings: list[str] = []

    raw_settings = raw.get("settings", {})
    if not isinstance(raw_settings, dict):
        raise ConfigError("[settings] must be a table")
    defaults = Settings()
    settings = Settings(
        hotkey=_as_str(raw_settings, "hotkey", defaults.hotkey),
        default_wheel=_as_str(raw_settings, "default_wheel"),
        notify=bool(raw_settings.get("notify", defaults.notify)),
        accent=raw_settings.get("accent") or None,
        overlay_mode=_as_str(raw_settings, "overlay_mode", defaults.overlay_mode),
        inner_radius=int(raw_settings.get("inner_radius", defaults.inner_radius)),
        outer_radius=int(raw_settings.get("outer_radius", defaults.outer_radius)),
    )
    if settings.overlay_mode not in OVERLAY_MODES:
        warnings.append(
            f"unknown overlay_mode {settings.overlay_mode!r}; "
            f"using {Settings().overlay_mode!r}"
        )
        settings.overlay_mode = Settings().overlay_mode
    if settings.outer_radius <= settings.inner_radius:
        warnings.append("outer_radius must exceed inner_radius; using defaults")
        settings.inner_radius = defaults.inner_radius
        settings.outer_radius = defaults.outer_radius

    raw_wheels = raw.get("wheel", [])
    if isinstance(raw_wheels, dict):        # tolerate a single [wheel] table
        raw_wheels = [raw_wheels]
    if not isinstance(raw_wheels, list):
        raise ConfigError("[[wheel]] must be a list of tables")

    wheels: list[Wheel] = []
    seen: set[str] = set()
    for position, raw_wheel in enumerate(raw_wheels, start=1):
        if not isinstance(raw_wheel, dict):
            warnings.append(f"wheel {position}: not a table, skipped")
            continue
        wheel_id = _as_str(raw_wheel, "id") or f"wheel{position}"
        if wheel_id in seen:
            warnings.append(f"wheel {position}: duplicate id {wheel_id!r}, skipped")
            continue
        seen.add(wheel_id)

        raw_items = raw_wheel.get("item", [])
        if isinstance(raw_items, dict):
            raw_items = [raw_items]
        items: list[Item] = []
        for index, raw_item in enumerate(raw_items or [], start=1):
            if not isinstance(raw_item, dict):
                warnings.append(f"{wheel_id} item {index}: not a table, skipped")
                continue
            item = Item(
                label=_as_str(raw_item, "label"),
                type=_as_str(raw_item, "type", "snippet"),
                value=_as_str(raw_item, "value"),
                icon=raw_item.get("icon") or None,
                shell=bool(raw_item.get("shell", False)),
            )
            problems = item.validate(f"{wheel_id} item {index}")
            if problems:
                warnings.extend(problems)
                continue
            items.append(item)
        wheels.append(Wheel(id=wheel_id, name=_as_str(raw_wheel, "name"), items=items))

    if not wheels:
        raise ConfigError("no usable [[wheel]] found in config")

    # A wheel item pointing at a wheel that does not exist would dead-end.
    ids = {wheel.id for wheel in wheels}
    for wheel in wheels:
        for item in wheel.items:
            if item.type == "wheel" and item.value not in ids:
                warnings.append(
                    f"{wheel.id}: item {item.label!r} points at unknown wheel "
                    f"{item.value!r}"
                )

    return Config(settings=settings, wheels=wheels, warnings=warnings)


def ensure_exists(path: Path | None = None) -> Path:
    """Create the config from the bundled example if it is not there yet."""
    path = path or config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(EXAMPLE, encoding="utf-8")
    return path


def load(path: Path | None = None) -> Config:
    path = path or config_path()
    if not path.exists():
        raise ConfigError(f"no config at {path} - run `qam install` first")
    return parse(path.read_text(encoding="utf-8"))


def save(config: Config, path: Path | None = None) -> Path:
    """Write the config out atomically, so a crash cannot truncate it."""
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".config.", suffix=".toml")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(tomlwrite.dumps(config))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return path


class ConfigStore:
    """Holds the live config and reloads it when the file changes on disk.

    Keeps the last good config if a reload fails, so a typo while editing never
    leaves the daemon without a wheel to show; the error surfaces as a warning
    in the wheel footer instead.
    """

    def __init__(self, path: Path | None = None):
        self.path = path or config_path()
        self.config = load(self.path)
        self._monitor = None
        self._on_change: Callable[[Config], None] | None = None
        self._suppress = 0        # ignore the reload our own save() triggers

    def watch(self, on_change: Callable[[Config], None]) -> None:
        """Start watching the file. Requires a running GLib main loop."""
        from gi.repository import Gio          # imported late: keeps this module importable without GTK

        self._on_change = on_change
        gfile = Gio.File.new_for_path(str(self.path))
        self._monitor = gfile.monitor_file(Gio.FileMonitorFlags.WATCH_MOVES, None)
        self._monitor.set_rate_limit(300)
        self._monitor.connect("changed", self._on_file_event)

    def _on_file_event(self, _monitor, _file, _other, event) -> None:
        from gi.repository import Gio

        interesting = (
            Gio.FileMonitorEvent.CHANGES_DONE_HINT,
            Gio.FileMonitorEvent.CREATED,
            Gio.FileMonitorEvent.MOVED_IN,
            Gio.FileMonitorEvent.RENAMED,
        )
        if event not in interesting:
            return
        if self._suppress > 0:
            self._suppress -= 1
            return
        self.reload()

    def reload(self) -> bool:
        try:
            self.config = load(self.path)
        except (ConfigError, OSError) as exc:
            self.config.warnings = [f"reload failed, keeping previous config: {exc}"]
        if self._on_change:
            self._on_change(self.config)
        return True

    def save(self, config: Config) -> None:
        """Persist a config and adopt it without bouncing through the watcher."""
        self._suppress += 1
        save(config, self.path)
        self.config = config
        if self._on_change:
            self._on_change(config)
