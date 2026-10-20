from __future__ import annotations

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


ISOLATED = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def git(where: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(where), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        check=True,
        capture_output=True,
        text=True,
        env=ISOLATED,
    )
    return done.stdout


def archive(folder: Path, tag: str) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        data = f'VERSION = "{tag[1:]}"\n'.encode()
        info = tarfile.TarInfo(f"anypatch-{tag[1:]}/src/anypatch/version.py")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    folder.mkdir(exist_ok=True)
    (folder / f"{tag}.tar.gz").write_bytes(buffer.getvalue())


def checkout(tmp_path: Path, tag: str | None) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True, env=ISOLATED
    )
    work = tmp_path / "work"
    subprocess.run(
        ["git", "clone", "-q", str(remote), str(work)],
        check=True,
        capture_output=True,
        env=ISOLATED,
    )
    (work / "scripts").mkdir()
    for name in ("publish-formula.sh", "update-formula.sh"):
        shutil.copy(ROOT / "scripts" / name, work / "scripts" / name)
    (work / "Formula").mkdir()
    (work / "Formula" / "anypatch.rb").write_text(TEMPLATE)
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "chore: start")
    if tag is not None:
        git(work, "tag", tag)
    git(work, "push", "-q", "--tags", "origin", "main")
    return work, remote


def publish(work: Path, remote: Path, tags: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **ISOLATED,
        "GITHUB_TOKEN": "unused-by-a-file-remote",
        "GITHUB_REPOSITORY": "gufranco/anypatch",
        "FORMULA_BOT_NAME": "github-actions[bot]",
        "FORMULA_BOT_EMAIL": "bot@example.invalid",
        "FORMULA_REMOTE": str(remote),
        "ANYPATCH_ARCHIVE_BASE": f"file://{tags}",
    }
    script = work / "scripts" / "publish-formula.sh"
    return subprocess.run(
        ["bash", str(script)], cwd=work, capture_output=True, text=True, env=env, check=False
    )


class TestPublishFormula:
    def test_it_commits_the_formula_for_the_newest_tag_and_pushes_it(self, tmp_path):
        # Arrange
        work, remote = checkout(tmp_path, "v0.1.0")
        archive(tmp_path / "tags", "v0.1.0")

        # Act
        result = publish(work, remote, tmp_path / "tags")

        # Assert
        assert result.returncode == 0
        assert result.stdout.endswith("formula published for v0.1.0\n")
        pushed = git(remote, "log", "-1", "--format=%s%n%an", "main")
        assert pushed == "chore(formula): point at v0.1.0 [skip ci]\ngithub-actions[bot]\n"

    def test_without_a_tag_there_is_nothing_to_publish(self, tmp_path):
        # Arrange
        work, remote = checkout(tmp_path, None)

        # Act
        result = publish(work, remote, tmp_path / "tags")

        # Assert
        assert result.returncode == 0
        assert result.stdout == "no tag exists yet, nothing to point the formula at\n"
        assert git(remote, "log", "-1", "--format=%s", "main") == "chore: start\n"

    def test_a_formula_already_at_the_tag_is_left_alone(self, tmp_path):
        # Arrange
        work, remote = checkout(tmp_path, "v0.1.0")
        archive(tmp_path / "tags", "v0.1.0")
        publish(work, remote, tmp_path / "tags")

        # Act
        result = publish(work, remote, tmp_path / "tags")

        # Assert
        assert result.returncode == 0
        assert result.stdout.endswith("the formula already points at v0.1.0\n")
