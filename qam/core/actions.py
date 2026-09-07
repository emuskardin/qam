"""Turning a selected Item into something happening on the machine.

Each item type maps to one small handler registered in HANDLERS, so adding a
new type later is a single function plus an entry in model.ITEM_TYPES.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .model import Item
from ..platform.base import Platform


@dataclass(slots=True)
class Outcome:
    """What the overlay should do and say after an item was picked."""

    message: str = ""
    detail: str = ""
    toast: str = ""                 # short confirmation shown in the wheel
    switch_to: str | None = None    # wheel id to jump to instead of closing
    error: bool = False


def _summarise(text: str, limit: int = 72) -> str:
    flattened = " ".join(text.split())
    return flattened if len(flattened) <= limit else flattened[: limit - 1] + "…"


def _snippet(item: Item, platform: Platform) -> Outcome:
    platform.set_clipboard(item.value)
    return Outcome(
        message="Copied", detail=_summarise(item.value), toast="Copied to clipboard"
    )


def _command(item: Item, platform: Platform) -> Outcome:
    platform.run_command(item.value, shell=item.shell)
    return Outcome(message="Ran", detail=_summarise(item.value), toast="Command started")


def _app(item: Item, platform: Platform) -> Outcome:
    platform.launch_app(item.value)
    return Outcome(message="Launched", detail=item.label, toast=f"Launched {item.label}")


def _path(item: Item, platform: Platform) -> Outcome:
    platform.open_path(item.value)
    return Outcome(
        message="Opened", detail=os.path.expanduser(item.value), toast="Opened"
    )


def _uri(item: Item, platform: Platform) -> Outcome:
    platform.open_uri(item.value)
    return Outcome(message="Opened", detail=_summarise(item.value), toast="Opened")


def _wheel(item: Item, _platform: Platform) -> Outcome:
    return Outcome(switch_to=item.value)


HANDLERS = {
    "snippet": _snippet,
    "command": _command,
    "app": _app,
    "path": _path,
    "uri": _uri,
    "wheel": _wheel,
}


def execute(item: Item, platform: Platform) -> Outcome:
    """Run an item's action. Never raises: failures come back as an Outcome."""
    handler = HANDLERS.get(item.type)
    if handler is None:
        return Outcome(message="Unknown item type", detail=item.type, error=True)
    try:
        return handler(item, platform)
    except Exception as exc:                      # noqa: BLE001 - surfaced to the user
        return Outcome(message=f"{item.label} failed", detail=str(exc), error=True)
