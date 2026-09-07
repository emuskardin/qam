"""Platform backends. Only this package may contain OS-specific code.

Each supported desktop lives in its own subpackage implementing the Platform
protocol in `base.py`; nothing outside here knows which one is in use.
"""

from __future__ import annotations

import sys

from .base import Platform


def detect() -> Platform:
    """Return the backend for the desktop we are running on."""
    if sys.platform.startswith("linux"):
        from .gnome import GnomePlatform

        return GnomePlatform()
    raise NotImplementedError(
        f"qam has no backend for {sys.platform} yet; add one under "
        "qam/platform/ implementing the Platform protocol"
    )
