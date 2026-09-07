"""Edit mode: putting the item editor on screen and writing the result back.

Kept apart from the daemon because it is the only part of the running app that
mutates the user's config, and that is worth being able to read in one piece.
"""

from __future__ import annotations

from ..core import config as config_module
from ..core.model import Config, Item
from ..ui import editor


class EditSession:
    """Owns the editor panel while it is open, and persists what it produces."""

    def __init__(self, daemon):
        self.daemon = daemon
        self.panel: editor.ItemEditor | None = None

    @property
    def open(self) -> bool:
        return self.panel is not None

    # ------------------------------------------------------------------ open
    def edit(self, wheel_index: int, item_index: int | None) -> None:
        window = self.daemon.window
        if self.open or window is None:
            return
        wheels = self.daemon.config.wheels
        if not 0 <= wheel_index < len(wheels):
            return
        wheel = wheels[wheel_index]
        item = (
            wheel.items[item_index]
            if item_index is not None and 0 <= item_index < len(wheel.items)
            else None
        )

        def done(new_item: Item | None, delete: bool) -> None:
            self.close()
            if delete and item_index is not None:
                self.delete(wheel_index, item_index)
            elif new_item is not None:
                self.commit(wheel_index, item_index, new_item)

        self.panel = editor.ItemEditor(item, done, self._paste)
        window.overlay.add_overlay(self.panel)
        window.set_editing(True, "editing a slice")
        self.panel.focus_first()

    def _paste(self, panel: editor.ItemEditor) -> None:
        # The wheel holds keyboard focus while it is open, which on Wayland is
        # exactly the condition under which the clipboard can be read at all.
        self.daemon.platform.read_clipboard(panel.set_value)

    def close(self) -> None:
        window = self.daemon.window
        if self.panel is None or window is None:
            return
        window.overlay.remove_overlay(self.panel)
        self.panel = None
        window.set_editing(False)
        window.grab_focus()

    # ----------------------------------------------------------------- write
    def commit(self, wheel_index: int, item_index: int | None, item: Item) -> None:
        updated = self.daemon.config.copy()
        wheel = updated.wheels[wheel_index]
        if item_index is None or not 0 <= item_index < len(wheel.items):
            wheel.items.append(item)
        else:
            wheel.items[item_index] = item
        self._persist(updated, "Saved", item.label)

    def delete(self, wheel_index: int, item_index: int) -> None:
        updated = self.daemon.config.copy()
        wheel = updated.wheels[wheel_index]
        if not 0 <= item_index < len(wheel.items):
            return
        removed = wheel.items.pop(item_index)
        self._persist(updated, "Removed", removed.label)

    def _persist(self, updated: Config, message: str, detail: str) -> None:
        window = self.daemon.window
        try:
            self.daemon.store.save(updated)
        except OSError as exc:
            window.show_flash("Could not save", str(exc), error=True)
            return
        window.hovered = None
        window.heat.clear()
        window.show_flash(message, detail)
