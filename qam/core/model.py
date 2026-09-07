"""Data model for wheels and their items. Platform independent."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

# Item types and the icon each falls back to when the config names none.
ITEM_TYPES: dict[str, str] = {
    "snippet": "edit-copy-symbolic",
    "command": "utilities-terminal-symbolic",
    "app": "application-x-executable-symbolic",
    "path": "folder-symbolic",
    "uri": "web-browser-symbolic",
    "wheel": "view-more-symbolic",
}

# What the hub shows underneath the label, per type.
TYPE_HINTS: dict[str, str] = {
    "snippet": "copy to clipboard",
    "command": "run",
    "app": "launch",
    "path": "open",
    "uri": "open",
    "wheel": "switch wheel",
}


class ConfigError(Exception):
    """Raised when a config file cannot be turned into a usable Config."""


@dataclass(slots=True)
class Item:
    label: str
    type: str = "snippet"
    value: str = ""
    icon: str | None = None
    shell: bool = False

    @property
    def icon_name(self) -> str:
        return self.icon or ITEM_TYPES.get(self.type, "application-x-executable-symbolic")

    @property
    def hint(self) -> str:
        return TYPE_HINTS.get(self.type, "")

    def validate(self, where: str) -> list[str]:
        problems = []
        if not self.label.strip():
            problems.append(f"{where}: item has an empty label")
        if self.type not in ITEM_TYPES:
            problems.append(
                f"{where}: unknown type {self.type!r} "
                f"(expected one of {', '.join(sorted(ITEM_TYPES))})"
            )
        if not self.value.strip() and self.type != "snippet":
            problems.append(f"{where}: item {self.label!r} has an empty value")
        return problems


@dataclass(slots=True)
class Wheel:
    id: str
    name: str = ""
    items: list[Item] = field(default_factory=list)

    @property
    def title(self) -> str:
        return self.name or self.id

    def validate(self, where: str) -> list[str]:
        problems = []
        if not self.id.strip():
            problems.append(f"{where}: wheel has an empty id")
        for index, item in enumerate(self.items):
            problems.extend(item.validate(f"{where} item {index + 1}"))
        return problems


@dataclass(slots=True)
class Settings:
    hotkey: str = "<Alt>q"
    default_wheel: str = ""
    notify: bool = True
    accent: str | None = None          # e.g. "#3584e4"; None follows the system accent
    # How the overlay surface is put on screen. GNOME composites nothing behind
    # a true fullscreen surface, so a transparent one shows black instead of the
    # desktop; "maximized" covers the work area and composites correctly.
    overlay_mode: str = "maximized"    # maximized | fullscreen | window
    inner_radius: int = 96
    outer_radius: int = 250


@dataclass(slots=True)
class Config:
    settings: Settings = field(default_factory=Settings)
    wheels: list[Wheel] = field(default_factory=list)
    # Non-fatal complaints about the file we loaded; shown in the wheel footer.
    warnings: list[str] = field(default_factory=list)

    def wheel_index(self, wheel_id: str) -> int | None:
        for index, wheel in enumerate(self.wheels):
            if wheel.id == wheel_id:
                return index
        return None

    def start_index(self) -> int:
        """Index of the wheel to open on, honouring settings.default_wheel."""
        if self.settings.default_wheel:
            found = self.wheel_index(self.settings.default_wheel)
            if found is not None:
                return found
        return 0

    def copy(self) -> Config:
        """Deep-enough copy for edit-then-save without mutating the live config."""
        return replace(
            self,
            settings=replace(self.settings),
            wheels=[
                Wheel(w.id, w.name, [replace(i) for i in w.items]) for w in self.wheels
            ],
            warnings=list(self.warnings),
        )
