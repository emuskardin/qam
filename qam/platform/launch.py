"""Process launching shared by desktop backends."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path


def run_command(command: str, shell: bool = False) -> None:
    argv = ["/bin/sh", "-c", command] if shell else shlex.split(command)
    if not argv:
        raise RuntimeError("empty command")
    # Commands are user-facing shortcuts, so resolve relative arguments from
    # the user's home rather than from whichever directory started the daemon
    # (a source checkout when running a development install, for example).
    # start_new_session and disconnected stdio make the launch non-blocking and
    # independent of qam's own process and terminal.
    subprocess.Popen(
        argv,
        cwd=Path.home(),
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
