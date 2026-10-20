from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = (
    "class Anypatch < Formula\n"
    '  url "https://github.com/gufranco/anypatch/archive/refs/tags/v0.0.0.tar.gz"\n'
    '  sha256 "' + "0" * 64 + '"\n'
    "end\n"
)


def archive(folder: Path, tag: str, recorded: str) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        data = f'VERSION = "{recorded}"\n'.encode()
        info = tarfile.TarInfo(f"anypatch-{tag[1:]}/src/anypatch/version.py")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    (folder / f"{tag}.tar.gz").write_bytes(buffer.getvalue())
    return buffer.getvalue()


def project(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "update-formula.sh", tmp_path / "scripts" / "update-formula.sh")
    (tmp_path / "Formula").mkdir()
    (tmp_path / "Formula" / "anypatch.rb").write_text(TEMPLATE)
    (tmp_path / "tags").mkdir()
    return tmp_path


def run(root: Path, tag: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "ANYPATCH_ARCHIVE_BASE": f"file://{root / 'tags'}"}
    script = root / "scripts" / "update-formula.sh"
    return subprocess.run(
        ["bash", str(script), tag], capture_output=True, text=True, env=env, check=False
    )


class TestUpdateFormula:
    def test_it_points_the_formula_at_the_tag_and_its_checksum(self, tmp_path):
        # Arrange
        root = project(tmp_path)
        data = archive(root / "tags", "v0.3.0", "0.3.0")

        # Act
        result = run(root, "v0.3.0")

        # Assert
        formula = (root / "Formula" / "anypatch.rb").read_text()
        assert result.returncode == 0
        assert f'url "file://{root / "tags"}/v0.3.0.tar.gz"' in formula
        assert f'sha256 "{hashlib.sha256(data).hexdigest()}"' in formula

    def test_a_tag_whose_code_carries_another_version_is_refused(self, tmp_path):
        # Arrange
        root = project(tmp_path)
        archive(root / "tags", "v0.3.0", "0.2.9")

        # Act
        result = run(root, "v0.3.0")

        # Assert
        assert result.returncode == 1
        assert result.stderr.startswith(
            "the release is tagged v0.3.0 but the code in it says 0.2.9"
        )
        assert (root / "Formula" / "anypatch.rb").read_text() == TEMPLATE

    def test_a_tag_that_cannot_be_downloaded_is_refused(self, tmp_path):
        # Arrange
        root = project(tmp_path)

        # Act
        result = run(root, "v9.9.9")

        # Assert
        assert result.returncode == 1
        assert result.stderr.startswith("could not download")
        assert (root / "Formula" / "anypatch.rb").read_text() == TEMPLATE

    def test_an_archive_without_a_version_file_is_refused(self, tmp_path):
        # Arrange
        root = project(tmp_path)
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            info = tarfile.TarInfo("anypatch-0.3.0/README.md")
            tar.addfile(info, io.BytesIO(b""))
        (root / "tags" / "v0.3.0.tar.gz").write_bytes(buffer.getvalue())

        # Act
        result = run(root, "v0.3.0")

        # Assert
        assert result.returncode == 1
        assert result.stderr == "the release archive has no src/anypatch/version.py\n"
