"""Pure geometry for the wheel. No GTK, no platform code - unit testable.

Angle convention
----------------
Sector 0 is centred at 12 o'clock and sectors advance clockwise, matching the
weapon wheels in Witcher/RDR2/GTA. "Wheel angle" is measured in radians from
12 o'clock, increasing clockwise, in [0, 2*pi).

Screen coordinates have y growing downwards, so a point (dx, dy) relative to
the wheel centre has wheel angle atan2(dx, -dy).

Cairo measures angles from the +x axis, which in y-down space also advances
clockwise, so converting is just a quarter turn: cairo = wheel - pi/2.
"""

import math

TAU = math.tau


def wheel_angle(dx: float, dy: float) -> float:
    """Wheel angle of the vector (dx, dy) given in screen coordinates."""
    return math.atan2(dx, -dy) % TAU


def to_cairo_angle(angle: float) -> float:
    """Convert a wheel angle to the angle cairo's arc() expects."""
    return angle - math.pi / 2


def sector_span(count: int) -> float:
    """Angular width of one sector."""
    if count <= 0:
        raise ValueError("count must be positive")
    return TAU / count


def sector_center(index: int, count: int) -> float:
    """Wheel angle of the centre line of a sector."""
    return (index * sector_span(count)) % TAU


def sector_bounds(index: int, count: int, gap: float = 0.0) -> tuple[float, float]:
    """(start, end) wheel angles of a sector, shrunk by `gap` radians in total.

    The gap is split evenly between the two edges, so adjacent sectors end up
    separated by exactly `gap` radians of empty space.
    """
    span = sector_span(count)
    center = sector_center(index, count)
    half = (span - gap) / 2.0
    return center - half, center + half


def hit_test(
    dx: float,
    dy: float,
    count: int,
    inner_radius: float,
    outer_radius: float | None = None,
) -> int | None:
    """Which sector does the point (dx, dy) relative to centre select?

    Returns None inside the dead zone (radius < inner_radius) or, when
    `outer_radius` is given, beyond it. Note that we deliberately do *not*
    bound selection by the outer radius by default: flicking the pointer well
    past the wheel should still select, exactly as a gamepad stick does.
    """
    if count <= 0:
        return None
    distance = math.hypot(dx, dy)
    if distance < inner_radius:
        return None
    if outer_radius is not None and distance > outer_radius:
        return None
    span = sector_span(count)
    # Offset by half a sector so that sector 0 is *centred* on 12 o'clock
    # rather than starting there, then floor into a bucket.
    return int(((wheel_angle(dx, dy) + span / 2.0) % TAU) // span) % count


def sector_centroid(
    index: int, count: int, inner_radius: float, outer_radius: float
) -> tuple[float, float]:
    """Offset from the wheel centre to the visual middle of a sector."""
    angle = sector_center(index, count)
    radius = (inner_radius + outer_radius) / 2.0
    return math.sin(angle) * radius, -math.cos(angle) * radius


def step(index: int | None, delta: int, count: int) -> int:
    """Move the hovered index by `delta`, wrapping, starting from the top."""
    if count <= 0:
        raise ValueError("count must be positive")
    if index is None:
        return 0 if delta >= 0 else (count - 1)
    return (index + delta) % count
