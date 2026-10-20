from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-commits.sh"


def check(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True, check=False
    )


def message(tmp_path: Path, subject: str) -> Path:
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text(f"# a comment git adds\n{subject}\n\nbody\n")
    return path


def repository(tmp_path: Path, subjects: list[str], author: str = "t") -> Path:
    def git(*args: str) -> None:
        isolated = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        subprocess.run(
            ["git", "-C", str(tmp_path), *args], check=True, capture_output=True, env=isolated
        )

    git("init", "-q", "-b", "main")
    for subject in subjects:
        git(
            "-c",
            f"user.name={author}",
            "-c",
            "user.email=t@example.invalid",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            subject,
        )
    return tmp_path


class TestOneMessage:
    @pytest.mark.parametrize(
        "subject",
        ["feat: read gdiff patches", "fix(ips): keep the truncation size", "feat!: rename apply"],
    )
    def test_a_conventional_subject_passes(self, subject, tmp_path):
        # Arrange
        path = message(tmp_path, subject)

        # Act
        result = check("--message", str(path))

        # Assert
        assert result.returncode == 0

    @pytest.mark.parametrize(
        ("subject", "problem"),
        [
            ("Add gdiff", "the type must be one of"),
            ("feat: Read gdiff", "the description starts lowercase"),
            ("feat: read gdiff.", "the description ends without a full stop"),
            ("feat: " + "x" * 45, "the subject is 51 characters and the limit is 50"),
        ],
    )
    def test_a_subject_that_breaks_the_convention_is_named(self, subject, problem, tmp_path):
        # Arrange
        path = message(tmp_path, subject)

        # Act
        result = check("--message", str(path))

        # Assert
        assert result.returncode == 1
        assert result.stderr.startswith(f"{subject}: {problem}")


class TestARange:
    def test_every_subject_in_the_range_is_checked(self, tmp_path):
        # Arrange
        repo = repository(tmp_path, ["chore: start", "feat: good one", "Bad one"])

        # Act
        result = check("--range", "HEAD~2..HEAD", cwd=repo)

        # Assert
        assert result.returncode == 1
        assert result.stderr.startswith("Bad one: the type must be one of")

    def test_a_dependabot_commit_is_not_held_to_the_subject_rules(self, tmp_path):
        # Arrange
        subject = "build: bump prettier from 3.9.9 to 3.9.10 in the release-tooling group"
        repo = repository(tmp_path, ["chore: start", subject], author="dependabot[bot]")

        # Act
        result = check("--range", "HEAD~1..HEAD", cwd=repo)

        # Assert
        assert result.returncode == 0
        assert result.stderr == ""

    def test_a_range_git_cannot_read_is_an_error(self, tmp_path):
        # Arrange
        repo = repository(tmp_path, ["chore: start"])

        # Act
        result = check("--range", "nope..HEAD", cwd=repo)

        # Assert
        assert result.returncode == 2
        assert "cannot read the commit range nope..HEAD" in result.stderr

    def test_without_arguments_it_prints_the_usage(self):
        # Arrange
        args: tuple[str, ...] = ()

        # Act
        result = check(*args)

        # Assert
        assert result.returncode == 2
        assert result.stderr.startswith("usage: check-commits.sh")
