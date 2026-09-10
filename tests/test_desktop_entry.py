"""The desktop entry is how GNOME learns qam's name and icon, so the few fields
that have to be exactly right are worth pinning down."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from qam import APP_ID
from qam.platform.gnome import appicon


class DesktopEntry(unittest.TestCase):
    def entry(self, source_root=None) -> dict[str, str]:
        text = appicon.desktop_text(["/usr/bin/qam", "show"], source_root)
        self.assertTrue(text.startswith("[Desktop Entry]\n"))
        return dict(
            line.split("=", 1)
            for line in text.splitlines()[1:]
            if line
        )

    def test_the_icon_is_named_after_the_application_id(self):
        # GNOME finds the notification icon by matching the entry's basename and
        # its Icon key against the bus name the daemon claims.
        self.assertEqual(self.entry()["Icon"], APP_ID)
        self.assertEqual(appicon.desktop_path().name, f"{APP_ID}.desktop")

    def test_launching_the_entry_opens_the_wheel(self):
        self.assertEqual(self.entry()["Exec"], "/usr/bin/qam show")

    def test_a_source_checkout_gets_a_working_directory(self):
        self.assertEqual(self.entry("/src/qam")["Path"], "/src/qam")
        self.assertNotIn("Path", self.entry())

    def test_the_icon_is_installed_where_the_icon_theme_looks(self):
        path = appicon.icon_path()
        self.assertEqual(path.name, f"{APP_ID}.png")
        self.assertEqual(path.parent.parts[-3:], ("hicolor", "128x128", "apps"))

    def test_install_and_uninstall_manage_the_entry_and_icon(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source" / "assets").mkdir(parents=True)
            (root / "source" / "assets" / "icon.png").write_bytes(b"png")
            with mock.patch.dict("os.environ", {"XDG_DATA_HOME": str(root / "data")}):
                appicon.install(["/usr/bin/qam", "show"], str(root / "source"))
                self.assertTrue(appicon.desktop_path().is_file())
                self.assertEqual(appicon.icon_path().read_bytes(), b"png")
                self.assertTrue(appicon.status()[0])

                appicon.uninstall()
                self.assertFalse(appicon.desktop_path().exists())
                self.assertFalse(appicon.icon_path().exists())


if __name__ == "__main__":
    unittest.main()
