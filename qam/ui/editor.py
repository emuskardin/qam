"""In-wheel editing: a small panel floating over the hub.

Real GTK widgets rather than hand-drawn text: an entry that already handles
selection, IME and clipboard is worth far more here than visual purity.
"""

from __future__ import annotations

from pathlib import Path

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
FEATURED_ICONS = (
    "applications-system-symbolic", "document-edit-symbolic", "folder-symbolic",
    "folder-open-symbolic", "text-x-generic-symbolic", "terminal-symbolic",
    "system-run-symbolic", "web-browser-symbolic", "mail-send-symbolic",
    "starred-symbolic", "emblem-favorite-symbolic", "camera-photo-symbolic",
    "image-x-generic-symbolic", "media-playback-start-symbolic",
    "preferences-system-symbolic", "system-search-symbolic", "view-more-symbolic",
)
AUTOMATIC_ICON = "Automatic (use item type default)"
BROWSE_ALL_ICONS = "Browse all installed icons…"


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

        icon_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon_row.append(Gtk.Label(label="Icon", xalign=0))
        self.icon_entry = Gtk.Entry(placeholder_text="Custom icon name (optional)")
        self.icon_entry.set_text(item.icon or "" if item else "")
        self.icon_entry.set_hexpand(True)
        self.icon_preview = Gtk.Image.new_from_icon_name(item.icon_name if item else "")
        self.icon_preview.set_pixel_size(20)
        icon_row.append(self.icon_entry)
        icon_row.append(self.icon_preview)
        self.append(icon_row)

        # These names are supplied by the active icon theme. The text field
        # remains available for a custom application icon name or a pasted one.
        self._icon_names = sorted(Gtk.IconTheme.get_for_display(
            Gdk.Display.get_default()
        ).get_icon_names())
        self._featured_icon_names = [
            name for name in FEATURED_ICONS if name in self._icon_names
        ]
        self._icon_syncing = False
        picker_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        picker_row.append(Gtk.Label(label="Choose an installed icon", xalign=0))
        self.icon_picker = Gtk.DropDown()
        self.icon_picker.set_factory(self._icon_factory())
        self.icon_picker.set_hexpand(True)
        self.icon_picker.set_tooltip_text("Choose an icon from the current theme")
        self._set_icon_choices(item.icon if item else "")
        self.icon_picker.connect("notify::selected", self._on_icon_selected)
        self.icon_entry.connect("changed", self._on_icon_changed)
        picker_row.append(self.icon_picker)
        self.append(picker_row)

        choose_file = Gtk.Button(label="Use image file…")
        choose_file.set_tooltip_text("Choose a PNG, SVG, or other image as a custom icon")
        choose_file.connect("clicked", self._choose_icon_file)
        self.append(choose_file)

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
        self._on_icon_changed(self.icon_entry)

    def _on_key(self, _controller, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            self.on_done(None, False)
            return True
        return False

    def _on_type_toggled(self, button, name):
        if button.get_active():
            self._sync_placeholder(name)
            if not self.icon_entry.get_text().strip():
                self.icon_preview.set_from_icon_name(self.current_default_icon())

    def _sync_placeholder(self, name):
        self.value_entry.set_placeholder_text(PLACEHOLDERS.get(name, ""))

    def _on_icon_selected(self, picker, _property):
        if self._icon_syncing:
            return
        selected = picker.get_selected()
        choice = self._picker_names[selected]
        if choice == BROWSE_ALL_ICONS:
            self._set_icon_choices(self.icon_entry.get_text().strip(), all_icons=True)
            return
        self._icon_syncing = True
        self.icon_entry.set_text("" if choice == AUTOMATIC_ICON else choice)
        self._icon_syncing = False

    def _on_icon_changed(self, entry):
        name = entry.get_text().strip()
        image_path = Path(name).expanduser()
        if name and image_path.is_file():
            self.icon_preview.set_from_file(str(image_path))
        else:
            self.icon_preview.set_from_icon_name(name or self.current_default_icon())
        if self._icon_syncing:
            return
        self._icon_syncing = True
        selected = self._picker_names.index(name) if name in self._picker_names else 0
        self.icon_picker.set_selected(selected)
        self._icon_syncing = False

    def _set_icon_choices(self, selected_name: str, all_icons: bool = False):
        """Start compact, then expose the complete theme on request."""
        names = self._icon_names if all_icons else self._featured_icon_names
        self._picker_names = [AUTOMATIC_ICON, *names]
        if not all_icons:
            self._picker_names.append(BROWSE_ALL_ICONS)
        self._icon_syncing = True
        self.icon_picker.set_model(Gtk.StringList.new(self._picker_names))
        self.icon_picker.set_selected(
            self._picker_names.index(selected_name) if selected_name in self._picker_names else 0
        )
        self._icon_syncing = False

    def _icon_factory(self):
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup_icon_row)
        factory.connect("bind", self._bind_icon_row)
        return factory

    def _setup_icon_row(self, _factory, list_item):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        image = Gtk.Image()
        image.set_pixel_size(18)
        label = Gtk.Label(xalign=0)
        label.set_hexpand(True)
        row.append(image)
        row.append(label)
        list_item.set_child(row)

    def _bind_icon_row(self, _factory, list_item):
        name = list_item.get_item().get_string()
        row = list_item.get_child()
        image = row.get_first_child()
        label = image.get_next_sibling()
        if name == AUTOMATIC_ICON:
            image.set_from_icon_name(self.current_default_icon())
        elif name == BROWSE_ALL_ICONS:
            image.set_from_icon_name("view-more-symbolic")
        else:
            image.set_from_icon_name(name)
        label.set_text(name)

    def _choose_icon_file(self, _button):
        chooser = Gtk.FileChooserNative.new(
            "Choose custom icon", self.get_root(), Gtk.FileChooserAction.OPEN,
            "Select", "Cancel",
        )
        image_filter = Gtk.FileFilter()
        image_filter.set_name("Image files")
        image_filter.add_pixbuf_formats()
        image_filter.add_mime_type("image/svg+xml")
        chooser.add_filter(image_filter)
        chooser.connect("response", self._on_icon_file_chosen)
        self._icon_file_chooser = chooser  # retain it until its callback runs
        chooser.show()

    def _on_icon_file_chosen(self, chooser, response):
        if response == Gtk.ResponseType.ACCEPT:
            icon_file = chooser.get_file()
            if icon_file and icon_file.get_path():
                self.icon_entry.set_text(icon_file.get_path())
        self._icon_file_chooser = None

    def current_default_icon(self) -> str:
        return ITEM_TYPES.get(self.current_type(), "application-x-executable-symbolic")

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
  background-color: alpha(@window_bg_color, 0.97);
  border: 1px solid alpha(@window_fg_color, 0.14);
  border-radius: 16px;
  padding: 18px;
  box-shadow: 0 18px 48px alpha(#000000, 0.35);
}
"""


def install_css():
    provider = Gtk.CssProvider()
    provider.load_from_string(EDITOR_CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    Adw.init()
