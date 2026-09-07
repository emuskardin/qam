"""A minimal TOML serialiser for qam's config schema.

The standard library ships `tomllib` for reading but nothing for writing, and
qam's schema is small and flat, so a purpose-built writer is cheaper and more
predictable than taking on a dependency. It handles exactly what `Config`
contains: strings, booleans, integers and arrays of tables.
"""

from __future__ import annotations

from .model import Config, Settings

_DEFAULTS = Settings()

_BASIC_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def quote(value: str) -> str:
    """Render a Python string as a TOML basic string."""
    out = [""]
    for char in value:
        if char in _BASIC_ESCAPES:
            out.append(_BASIC_ESCAPES[char])
        elif char < " " or char == "\x7f":
            out.append(f"\\u{ord(char):04X}")
        else:
            out.append(char)
    return '"' + "".join(out) + '"'


def _render(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return quote(value)
    raise TypeError(f"cannot serialise {type(value).__name__} to TOML")


def _pair(key: str, value: object, indent: str = "") -> str:
    return f"{indent}{key} = {_render(value)}\n"


def dumps(config: Config) -> str:
    """Serialise a Config to TOML text that `tomllib` can read back."""
    out = [
        "# qam configuration\n",
        "# Written by qam. Hand edits are picked up live - no restart needed.\n",
        "# Note: editing inside the wheel rewrites this file and drops comments.\n",
        "\n[settings]\n",
    ]
    settings = config.settings
    out.append(_pair("hotkey", settings.hotkey))
    if settings.default_wheel:
        out.append(_pair("default_wheel", settings.default_wheel))
    out.append(_pair("notify", settings.notify))
    if settings.accent:
        out.append(_pair("accent", settings.accent))
    for name in ("overlay_mode", "inner_radius", "outer_radius"):
        value = getattr(settings, name)
        if value != getattr(_DEFAULTS, name):
            out.append(_pair(name, value))

    for wheel in config.wheels:
        out.append("\n[[wheel]]\n")
        out.append(_pair("id", wheel.id))
        if wheel.name:
            out.append(_pair("name", wheel.name))
        for item in wheel.items:
            out.append("\n  [[wheel.item]]\n")
            out.append(_pair("label", item.label, "  "))
            out.append(_pair("type", item.type, "  "))
            out.append(_pair("value", item.value, "  "))
            if item.icon:
                out.append(_pair("icon", item.icon, "  "))
            if item.shell:
                out.append(_pair("shell", item.shell, "  "))
    return "".join(out)
