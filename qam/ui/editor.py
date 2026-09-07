"""In-wheel editing: a small panel floating over the hub.

Real GTK widgets rather than hand-drawn text: an entry that already handles
selection, IME and clipboard is worth far more here than visual purity.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

from ..core.model import ITEM_TYPES, Item  # noqa: E402

TYPE_ORDER = ["snippet", "command", "app", "path", "uri", "wheel"]
TYPE_LABELS = {
    "snippet": "Snippet",
    "command": "Command",
    "app": "App",
    "path": "Path",
    "uri": "URL",
    "wheel": "Wheel",
}
PLACEHOLDERS = {
    "snippet": "text to copy, e.g. kubectl get pods -A",
    "command": "command to run",
    "app": "org.gnome.Nautilus.desktop",
    "path": "~/Documents/notes.md",
    "uri": "https://example.com",
    "wheel": "id of the wheel to jump to",
}


class ItemEditor(Gtk.Box):
    """Edit one item. `on_done(item | None, delete: bool)` closes the panel."""

    def __init__(self, item: Item | None, on_done, on_paste):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.on_done = on_done
        self.on_paste = on_paste
        self.existing = item is not None
        self.add_css_class("qam-editor")
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.set_size_request(420, -1)

        title = Gtk.Label(label="Edit slice" if self.existing else "New slice")
        title.add_css_class("title-4")
        self.append(title)

        self.label_entry = Gtk.Entry(placeholder_text="Label shown on the wheel")
        self.label_entry.set_text(item.label if item else "")
        self.append(self.label_entry)

        self.type_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.type_row.add_css_class("linked")
        self.type_buttons: dict[str, Gtk.ToggleButton] = {}
        first: Gtk.ToggleButton | None = None
        current = item.type if item else "snippet"
        for name in TYPE_ORDER:
            button = Gtk.ToggleButton(label=TYPE_LABELS[name])
            button.set_hexpand(True)
            if first is None:
                first = button
            else:
                button.set_group(first)
            button.set_active(name == current)
            button.connect("toggled", self._on_type_toggled, name)
            self.type_buttons[name] = button
            self.type_row.append(button)
        self.append(self.type_row)

        self.value_entry = Gtk.Entry()
        self.value_entry.set_text(item.value if item else "")
        self.append(self.value_entry)

        self.icon_entry = Gtk.Entry(placeholder_text="icon name (optional)")
        self.icon_entry.set_text(item.icon or "" if item else "")
        self.append(self.icon_entry)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        buttons.set_homogeneous(True)
        paste = Gtk.Button(label="Paste clipboard")
        paste.connect("clicked", lambda *_: self.on_paste(self))
        buttons.append(paste)
        if self.existing:
            delete = Gtk.Button(label="Delete")
            delete.add_css_class("destructive-action")
            delete.connect("clicked", lambda *_: self.on_done(None, True))
            buttons.append(delete)
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_: self.on_done(None, False))
        buttons.append(cancel)
        save = Gtk.Button(label="Save")
        save.add_css_class("suggested-action")
        save.connect("clicked", lambda *_: self._save())
        buttons.append(save)
        self.append(buttons)

        for entry in (self.label_entry, self.value_entry, self.icon_entry):
            entry.connect("activate", lambda *_: self._save())

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

        self._sync_placeholder(current)

    def _on_key(self, _controller, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            self.on_done(None, False)
            return True
        return False

    def _on_type_toggled(self, button, name):
        if button.get_active():
            self._sync_placeholder(name)

    def _sync_placeholder(self, name):
        self.value_entry.set_placeholder_text(PLACEHOLDERS.get(name, ""))

    def current_type(self) -> str:
        for name, button in self.type_buttons.items():
            if button.get_active():
                return name
        return "snippet"

    def set_value(self, text: str):
        self.value_entry.set_text(text)
        if not self.label_entry.get_text().strip():
            words = " ".join(text.split())
            self.label_entry.set_text(words[:28] + ("…" if len(words) > 28 else ""))

    def focus_first(self):
        self.label_entry.grab_focus()

    def _save(self):
        item_type = self.current_type()
        label = self.label_entry.get_text().strip()
        value = self.value_entry.get_text()
        if not label:
            words = " ".join(value.split())
            label = words[:28] or TYPE_LABELS[item_type]
        if item_type not in ITEM_TYPES:
            item_type = "snippet"
        self.on_done(
            Item(
                label=label,
                type=item_type,
                value=value,
                icon=self.icon_entry.get_text().strip() or None,
            ),
            False,
        )


EDITOR_CSS = """
.qam-editor {
  background-color: alpha(#15171c, 0.97);
  border: 1px solid alpha(#ffffff, 0.14);
  border-radius: 16px;
  padding: 18px;
  box-shadow: 0 18px 48px alpha(#000000, 0.55);
}
"""


def install_css():
    provider = Gtk.CssProvider()
    provider.load_from_string(EDITOR_CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    Adw.init()
