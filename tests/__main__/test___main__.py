from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "anypatch", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(SRC)},
        check=False,
    )


class TestTheModuleForm:
    def test_it_reaches_the_same_command_line_as_the_script(self):
        # Arrange
        args = ("--version",)

        # Act
        result = run(*args)

        # Assert
        assert result.returncode == 0
        assert result.stdout.startswith("anypatch ")

    def test_it_carries_the_exit_status_of_a_bad_command(self):
        # Arrange
        args = ("no-such-command",)

        # Act
        result = run(*args)

        # Assert
        assert result.returncode == 2
        assert "__main__" not in result.stderr

    def test_it_calls_the_entry_point_the_script_calls(self):
        # Arrange
        from anypatch import __main__, entry

        # Act
        called = __main__.main

        # Assert
        assert called is entry.main
