"""GNOME backend, split by the three things it has to do: register the
hotkey, run as a service, and actually carry actions out."""

from .backend import GnomePlatform

__all__ = ["GnomePlatform"]
