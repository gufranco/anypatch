from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def project(tmp_path: Path, recorded: str) -> Path:
    (tmp_path / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "set-version.sh", tmp_path / "scripts" / "set-version.sh")
    package = tmp_path / "src" / "anypatch"
    package.mkdir(parents=True)
    (package / "version.py").write_text(recorded)
    return tmp_path


def run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    script = root / "scripts" / "set-version.sh"
    return subprocess.run(["bash", str(script), *args], capture_output=True, text=True, check=False)


class TestSetVersion:
    def test_it_writes_the_version_semantic_release_chose(self, tmp_path):
        # Arrange
        root = project(tmp_path, 'VERSION = "0.0.0"\n')

        # Act
        result = run(root, "0.2.1")

        # Assert
        assert result.returncode == 0
        assert result.stdout == "version set to 0.2.1\n"
        assert (root / "src" / "anypatch" / "version.py").read_text() == 'VERSION = "0.2.1"\n'

    def test_a_value_that_is_not_a_version_is_refused(self, tmp_path):
        # Arrange
        root = project(tmp_path, 'VERSION = "0.0.0"\n')

        # Act
        result = run(root, "latest")

        # Assert
        assert result.returncode == 1
        assert result.stderr == "not a version: latest\n"
        assert (root / "src" / "anypatch" / "version.py").read_text() == 'VERSION = "0.0.0"\n'

    def test_a_file_without_the_assignment_is_refused(self, tmp_path):
        # Arrange
        root = project(tmp_path, "NAME = 'anypatch'\n")

        # Act
        result = run(root, "1.0.0")

        # Assert
        assert result.returncode == 1
        assert "no VERSION assignment" in result.stderr
