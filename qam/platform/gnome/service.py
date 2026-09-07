"""Keeping the daemon resident through a systemd user service.

The daemon has to already be running when the hotkey is pressed - that is the
whole reason the wheel appears instantly - so it starts with the graphical
session rather than on demand.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

SERVICE_NAME = "qam.service"


def unit_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / "systemd" / "user"


def unit_path() -> Path:
    return unit_dir() / SERVICE_NAME


def systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", "--user", *args], capture_output=True, text=True, check=False
    )


def unit_text(executable: list[str], source_root: str | None) -> str:
    # Running from a source checkout rather than an installed package means
    # systemd cannot find `qam` on its own, so pin the path here.
    source = ""
    if source_root:
        source = (
            f"WorkingDirectory={source_root}\n"
            f"Environment=PYTHONPATH={source_root}\n"
        )
    return (
        "[Unit]\n"
        "Description=qam quick access menu daemon\n"
        "PartOf=graphical-session.target\n"
        "After=graphical-session.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={shlex.join(executable)}\n"
        f"{source}"
        "Restart=on-failure\n"
        "RestartSec=2\n"
        "Slice=app.slice\n"
        "\n"
        "[Install]\n"
        "WantedBy=graphical-session.target\n"
    )


def install(executable: list[str], source_root: str | None = None) -> str:
    unit_dir().mkdir(parents=True, exist_ok=True)
    unit = unit_path()
    unit.write_text(unit_text(executable, source_root), encoding="utf-8")
    systemctl("daemon-reload")
    # Restart rather than start: an install over a running daemon should pick
    # up the new unit, not silently keep the old process.
    result = systemctl("enable", SERVICE_NAME)
    restarted = systemctl("restart", SERVICE_NAME)
    if result.returncode != 0 or restarted.returncode != 0:
        detail = (result.stderr or restarted.stderr).strip()
        return f"wrote {unit} but could not start it: {detail}"
    return f"installed and started {unit}"


def uninstall() -> str:
    systemctl("disable", "--now", SERVICE_NAME)
    unit_path().unlink(missing_ok=True)
    systemctl("daemon-reload")
    return f"removed {unit_path()}"


def status() -> tuple[bool, str]:
    if not unit_path().exists():
        return False, "unit not installed - run `qam install`"
    active = systemctl("is-active", SERVICE_NAME).stdout.strip()
    return active == "active", f"systemd unit is {active or 'unknown'}"
