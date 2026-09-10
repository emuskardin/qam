"""Launching commands from wheel items must never hold up the wheel UI."""

import subprocess
import unittest
from pathlib import Path
from unittest import mock

from qam.platform import launch


class RunCommand(unittest.TestCase):
    @mock.patch.object(launch.subprocess, "Popen")
    def test_plain_command_is_started_detached_from_the_users_home(self, popen):
        launch.run_command("xdg-open Desktop/experiments.md")

        popen.assert_called_once_with(
            ["xdg-open", "Desktop/experiments.md"],
            cwd=Path.home(),
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @mock.patch.object(launch.subprocess, "Popen")
    def test_shell_commands_are_also_started_in_the_background(self, popen):
        launch.run_command("printf hello | xclip", shell=True)

        argv, = popen.call_args.args
        self.assertEqual(argv, ["/bin/sh", "-c", "printf hello | xclip"])
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertEqual(popen.call_args.kwargs["stdin"], subprocess.DEVNULL)


if __name__ == "__main__":
    unittest.main()
