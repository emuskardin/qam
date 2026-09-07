"""Geometry is the part that has to be right every single time: it decides
which slice a flick of the mouse selects."""

import math
import unittest

from qam.ui import geometry


class HitTest(unittest.TestCase):
    def test_cardinal_directions_pick_the_expected_slice(self):
        # Sector 0 is centred at 12 o'clock and they advance clockwise.
        for dx, dy, expected in [
            (0, -100, 0),    # up
            (100, -100, 1),  # up-right
            (100, 0, 2),     # right
            (100, 100, 3),   # down-right
            (0, 100, 4),     # down
            (-100, 100, 5),  # down-left
            (-100, 0, 6),    # left
            (-100, -100, 7), # up-left
        ]:
            self.assertEqual(geometry.hit_test(dx, dy, 8, 50), expected, (dx, dy))

    def test_every_angle_maps_into_range(self):
        for count in range(1, 13):
            seen = set()
            for degree in range(0, 360):
                angle = math.radians(degree)
                index = geometry.hit_test(
                    math.sin(angle) * 200, -math.cos(angle) * 200, count, 50
                )
                self.assertIsNotNone(index)
                self.assertTrue(0 <= index < count)
                seen.add(index)
            self.assertEqual(seen, set(range(count)), f"count={count}")

    def test_slice_boundaries_wrap_cleanly(self):
        # Just either side of 12 o'clock must land in slice 0, not wrap to 5.
        for degree in (-1, 0, 1):
            angle = math.radians(degree)
            index = geometry.hit_test(
                math.sin(angle) * 200, -math.cos(angle) * 200, 6, 50
            )
            self.assertEqual(index, 0, degree)

    def test_dead_zone_selects_nothing(self):
        self.assertIsNone(geometry.hit_test(0, 0, 6, 50))
        self.assertIsNone(geometry.hit_test(30, 30, 6, 50))
        self.assertIsNotNone(geometry.hit_test(0, -51, 6, 50))

    def test_flicking_far_past_the_wheel_still_selects(self):
        # A gamepad-style flick must not need to stop on the wheel itself.
        self.assertEqual(geometry.hit_test(0, -5000, 4, 50), 0)

    def test_outer_radius_bounds_selection_when_asked(self):
        self.assertIsNone(geometry.hit_test(0, -5000, 4, 50, outer_radius=250))

    def test_no_items_selects_nothing(self):
        self.assertIsNone(geometry.hit_test(0, -100, 0, 50))


class Sectors(unittest.TestCase):
    def test_bounds_cover_the_circle_without_overlap(self):
        count = 7
        total = sum(
            end - start
            for start, end in (geometry.sector_bounds(i, count) for i in range(count))
        )
        self.assertAlmostEqual(total, geometry.TAU)

    def test_gap_shrinks_each_sector_evenly(self):
        gap = math.radians(4)
        start, end = geometry.sector_bounds(0, 6, gap)
        self.assertAlmostEqual(end - start, geometry.sector_span(6) - gap)

    def test_centroid_of_the_top_slice_is_directly_above_centre(self):
        dx, dy = geometry.sector_centroid(0, 8, 100, 200)
        self.assertAlmostEqual(dx, 0.0)
        self.assertAlmostEqual(dy, -150.0)

    def test_span_rejects_an_empty_wheel(self):
        with self.assertRaises(ValueError):
            geometry.sector_span(0)


class Stepping(unittest.TestCase):
    def test_stepping_wraps_in_both_directions(self):
        self.assertEqual(geometry.step(5, 1, 6), 0)
        self.assertEqual(geometry.step(0, -1, 6), 5)

    def test_stepping_from_nothing_starts_at_an_end(self):
        self.assertEqual(geometry.step(None, 1, 6), 0)
        self.assertEqual(geometry.step(None, -1, 6), 5)


if __name__ == "__main__":
    unittest.main()
