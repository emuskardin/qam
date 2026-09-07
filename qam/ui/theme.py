"""Colours, metrics and easing for the wheel. No GTK types, no platform code."""

from __future__ import annotations

import math

RGBA = tuple[float, float, float, float]


def rgba(hex_colour: str, alpha: float = 1.0) -> RGBA:
    text = hex_colour.lstrip("#")
    if len(text) == 3:
        text = "".join(char * 2 for char in text)
    if len(text) != 6:
        raise ValueError(f"bad colour {hex_colour!r}")
    red, green, blue = (int(text[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    return red, green, blue, alpha


def mix(first: RGBA, second: RGBA, amount: float) -> RGBA:
    return tuple(a + (b - a) * amount for a, b in zip(first, second))  # type: ignore[return-value]


def with_alpha(colour: RGBA, alpha: float) -> RGBA:
    return colour[0], colour[1], colour[2], alpha


# The desktop stays fully visible: qam paints the wheel and nothing else.
# Only a soft shadow hugging the wheel separates it from whatever is behind.
BACKDROP: RGBA = (0.0, 0.0, 0.0, 0.0)

SECTOR_IDLE: RGBA = rgba("#1b1e26", 0.90)
SECTOR_HOVER_MIX = 0.90          # how far an active sector travels towards the accent
SECTOR_EDGE: RGBA = rgba("#ffffff", 0.10)
SECTOR_EDGE_ACTIVE: RGBA = rgba("#ffffff", 0.55)

HUB_FILL: RGBA = rgba("#0e1013", 0.90)
HUB_EDGE: RGBA = rgba("#ffffff", 0.12)

TEXT: RGBA = rgba("#f2f4f8", 0.96)
TEXT_DIM: RGBA = rgba("#f2f4f8", 0.68)
TEXT_ON_ACCENT: RGBA = rgba("#ffffff", 1.0)
WARNING: RGBA = rgba("#ff7b72", 0.95)

# The caption under the wheel sits directly on the desktop, so it carries its
# own backing plate - without one it is unreadable over a light wallpaper.
PLATE: RGBA = rgba("#0e1013", 0.80)
PLATE_EDGE: RGBA = rgba("#ffffff", 0.08)
PLATE_PAD_X = 13.0
PLATE_PAD_Y = 5.0
PLATE_GAP = 7.0                  # vertical space between caption pills
DOT_SPACING = 18.0               # between the wheel indicator dots
DOT_RADIUS = 4.0

SHADOW: RGBA = (0.0, 0.0, 0.0, 0.34)
SHADOW_SPREAD = 18.0             # px of soft shadow outside the wheel

DEFAULT_ACCENT: RGBA = rgba("#3584e4")

# Geometry (px, logical). Radii are overridable from [settings].
SECTOR_GAP = math.radians(2.4)   # empty wedge between neighbouring sectors
HOVER_LIFT = 12.0                # how far the active sector grows outwards
CORNER_INSET = 3.0

ICON_SIZE = 32
LABEL_SIZE = 12                  # pt
BADGE_SIZE = 9
HUB_TITLE_SIZE = 15
HUB_HINT_SIZE = 10
FOOTER_SIZE = 10
FONT = "Cantarell"

OPEN_MS = 150.0
CLOSE_MS = 100.0
SWITCH_MS = 130.0                # wheel-to-wheel cross-fade
HOVER_MS = 90.0                  # per-sector highlight travel


def ease_out_back(t: float, overshoot: float = 1.3) -> float:
    """Ease-out with a slight overshoot - the springy 'pop' when opening."""
    t = t - 1.0
    return 1.0 + (overshoot + 1.0) * t * t * t + overshoot * t * t


def ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return low if value < low else high if value > high else value
