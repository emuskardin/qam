"""Config loading has to survive whatever the user leaves in the file, and
what the in-wheel editor writes back has to be readable again."""

import tempfile
import unittest
from pathlib import Path

from qam.core import config, tomlwrite
from qam.core.model import Config, ConfigError, Item, Settings, Wheel


class Parsing(unittest.TestCase):
    def test_the_shipped_example_is_valid(self):
        parsed = config.parse(config.EXAMPLE)
        self.assertEqual([w.id for w in parsed.wheels], ["main", "dev"])
        self.assertEqual(parsed.warnings, [])
        self.assertEqual(parsed.wheels[0].items[0].value, "firefox.desktop")

    def test_checked_in_example_matches_the_installed_default(self):
        checked_in = Path("data/config.example.toml").read_text(encoding="utf-8")
        self.assertEqual(checked_in.rstrip(), config.EXAMPLE.rstrip())

    def test_missing_settings_fall_back_to_defaults(self):
        parsed = config.parse('[[wheel]]\nid = "a"\n')
        self.assertEqual(parsed.settings.hotkey, Settings().hotkey)

    def test_broken_toml_is_rejected_clearly(self):
        with self.assertRaises(ConfigError):
            config.parse("[[wheel]\nid =")

    def test_a_file_with_no_wheels_is_rejected(self):
        with self.assertRaises(ConfigError):
            config.parse("[settings]\nnotify = false\n")

    def test_a_bad_item_is_dropped_with_a_warning_not_a_crash(self):
        parsed = config.parse(
            '[[wheel]]\nid = "a"\n'
            '  [[wheel.item]]\n  label = "ok"\n  type = "snippet"\n  value = "x"\n'
            '  [[wheel.item]]\n  label = "bad"\n  type = "nonsense"\n  value = "y"\n'
        )
        self.assertEqual([i.label for i in parsed.wheels[0].items], ["ok"])
        self.assertTrue(any("nonsense" in w for w in parsed.warnings))

    def test_a_wheel_item_pointing_nowhere_warns(self):
        parsed = config.parse(
            '[[wheel]]\nid = "a"\n'
            '  [[wheel.item]]\n  label = "go"\n  type = "wheel"\n  value = "ghost"\n'
        )
        self.assertTrue(any("ghost" in w for w in parsed.warnings))

    def test_duplicate_wheel_ids_are_skipped(self):
        parsed = config.parse('[[wheel]]\nid = "a"\n[[wheel]]\nid = "a"\n')
        self.assertEqual(len(parsed.wheels), 1)

    def test_nonsense_radii_fall_back_instead_of_drawing_nothing(self):
        parsed = config.parse(
            "[settings]\ninner_radius = 400\nouter_radius = 100\n"
            '[[wheel]]\nid = "a"\n'
        )
        self.assertLess(parsed.settings.inner_radius, parsed.settings.outer_radius)

    def test_default_wheel_selects_the_starting_wheel(self):
        parsed = config.parse(
            '[settings]\ndefault_wheel = "b"\n[[wheel]]\nid = "a"\n[[wheel]]\nid = "b"\n'
        )
        self.assertEqual(parsed.start_index(), 1)

    def test_an_unknown_default_wheel_falls_back_to_the_first(self):
        parsed = config.parse('[settings]\ndefault_wheel = "gone"\n[[wheel]]\nid = "a"\n')
        self.assertEqual(parsed.start_index(), 0)


class RoundTrip(unittest.TestCase):
    def test_editor_output_parses_back_identically(self):
        original = config.parse(config.EXAMPLE)
        again = config.parse(tomlwrite.dumps(original))
        self.assertEqual(
            [(w.id, [(i.label, i.type, i.value) for i in w.items]) for w in again.wheels],
            [(w.id, [(i.label, i.type, i.value) for i in w.items]) for w in original.wheels],
        )

    def test_values_needing_escapes_survive(self):
        nasty = 'quote " backslash \\ tab \t newline \n done'
        written = Config(wheels=[Wheel("a", "A", [Item("odd", "snippet", nasty)])])
        again = config.parse(tomlwrite.dumps(written))
        self.assertEqual(again.wheels[0].items[0].value, nasty)

    def test_saving_is_atomic_and_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            source = config.parse(config.EXAMPLE)
            config.save(source, path)
            self.assertEqual(len(list(Path(directory).iterdir())), 1)  # no temp left behind
            self.assertEqual(len(config.load(path).wheels), len(source.wheels))


class Copying(unittest.TestCase):
    def test_copy_does_not_share_items_with_the_original(self):
        original = config.parse(config.EXAMPLE)
        duplicate = original.copy()
        duplicate.wheels[0].items[0].label = "changed"
        duplicate.wheels[0].items.append(Item("extra", "snippet", "x"))
        self.assertNotEqual(original.wheels[0].items[0].label, "changed")
        self.assertNotEqual(len(original.wheels[0].items), len(duplicate.wheels[0].items))


if __name__ == "__main__":
    unittest.main()
