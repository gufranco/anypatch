from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = "tests/repository/test_legal_hygiene.py"

_HK = "ha" + "ck"

INFRINGEMENT = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        rf"\b{_HK}",
        rf"\brom{_HK}",
        r"\bpirate",
        r"\bpirac",
        r"\bwarez",
        r"\bcrack",
        r"\bbootleg",
        r"\bkeygen",
        r"\block ?out",
        r"\bbypass",
        r"\bcircumvent",
        r"copy ?protection",
    )
)

NEUTRAL_TERM = (re.compile(r"\bdump", re.IGNORECASE),)

PUBLIC_TEXT = (
    "README.md",
    "README.ja.md",
    "README.zh-Hans.md",
    "README.zh-HK.md",
    "CHANGELOG.md",
    "NOTICE.md",
    "CITATION.cff",
    "pyproject.toml",
    "AGENTS.md",
    "CONTRIBUTING.md",
)

ARTIFACT_EXTENSIONS = (
    ".rom",
    ".nes",
    ".sfc",
    ".smc",
    ".gba",
    ".n64",
    ".z64",
    ".v64",
    ".gb",
    ".gbc",
    ".ips",
    ".bps",
    ".ups",
    ".ppf",
    ".aps",
    ".rup",
    ".xdelta",
    ".vcdiff",
    ".bsdiff",
    ".bsp",
    ".pat",
    ".dps",
    ".hdiff",
    ".jdf",
    ".gdiff",
    ".dldi",
    ".ebp",
    ".zps",
    ".pmsr",
    ".eep",
    ".sra",
    ".fla",
    ".mpk",
)

DIGEST_WIDTHS = {"crc32": 8, "md5": 32, "sha1": 40, "sha256": 64}


def tracked_files() -> list[str]:
    output = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return output.split()


def matches(text: str, patterns: tuple[re.Pattern[str], ...]) -> list[str]:
    return [pattern.pattern for pattern in patterns if pattern.search(text)]


def artifact_paths(paths: list[str]) -> list[str]:
    return [path for path in paths if path.lower().endswith(ARTIFACT_EXTENSIONS)]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def scan(patterns: tuple[re.Pattern[str], ...], paths: list[str]) -> dict[str, list[str]]:
    hits = {path: matches(read(path), patterns) for path in paths if path != GUARD}
    return {path: found for path, found in hits.items() if found}


def manifest_problems(artifact: dict[str, object]) -> list[str]:
    problems = [
        key for key in ("id", "title", "filename", "form", "provenance") if not artifact.get(key)
    ]
    accepted = artifact.get("accepted")
    if not isinstance(accepted, list) or not accepted:
        problems.append("accepted")
        return problems
    for entry in accepted:
        size = entry.get("size")
        if not isinstance(size, int) or size <= 0:
            problems.append("size")
        for name, width in DIGEST_WIDTHS.items():
            value = entry.get(name)
            if not isinstance(value, str) or re.fullmatch(rf"[0-9a-f]{{{width}}}", value) is None:
                problems.append(name)
    return problems


class TestTheDetectors:
    def test_an_infringement_term_is_found(self):
        # Arrange
        text = "this file is a CRACK and defeats the copy protection"

        # Act
        found = matches(text, INFRINGEMENT)

        # Assert
        assert found == [r"\bcrack", r"copy ?protection"]

    def test_ordinary_prose_matches_nothing(self):
        # Arrange
        text = "read, write, merge and convert binary patches for preservation"

        # Act
        found = matches(text, INFRINGEMENT)

        # Assert
        assert found == []

    def test_an_artifact_extension_is_reported(self):
        # Arrange
        paths = ["docs/readme.md", "saves/game.sra", "src/a.py"]

        # Act
        offenders = artifact_paths(paths)

        # Assert
        assert offenders == ["saves/game.sra"]

    def test_paths_without_an_artifact_extension_are_clean(self):
        # Arrange
        paths = ["src/a.py", "README.md"]

        # Act
        offenders = artifact_paths(paths)

        # Assert
        assert offenders == []


class TestTheRepositoryIsClean:
    def test_no_tracked_file_carries_infringement_vocabulary(self):
        # Arrange
        paths = tracked_files()

        # Act
        offenders = scan(INFRINGEMENT, paths)

        # Assert
        assert offenders == {}

    def test_no_public_text_file_calls_an_image_a_dump(self):
        # Arrange
        present = [path for path in PUBLIC_TEXT if (ROOT / path).exists()]

        # Act
        offenders = scan(NEUTRAL_TERM, present)

        # Assert
        assert offenders == {}

    def test_no_rom_bios_save_or_patch_file_is_tracked(self):
        # Arrange
        paths = tracked_files()

        # Act
        offenders = artifact_paths(paths)

        # Assert
        assert offenders == []

    def test_the_guard_is_exempt_from_its_own_scan(self):
        # Arrange
        paths = [GUARD]

        # Act
        offenders = scan(INFRINGEMENT, paths)

        # Assert
        assert offenders == {}


class TestTheArtifactManifestIsComplete:
    def test_a_fully_specified_artifact_has_no_problems(self):
        # Arrange
        artifact = {
            "id": "x",
            "title": "X",
            "filename": "x.bin",
            "form": "whole file",
            "provenance": "supplied by the developer",
            "accepted": [
                {
                    "size": 5,
                    "crc32": "dc450446",
                    "md5": "d2ca2614754d49b2d09f68e982f675cc",
                    "sha1": "a76dc32cdb38cb0c577130ad8d35339c3c3164e9",
                    "sha256": "4ae3e01ec8db638a7f4106763ecb8b921c0411e8009aa1ebfade1a34fb93c91a",
                }
            ],
        }

        # Act
        problems = manifest_problems(artifact)

        # Assert
        assert problems == []

    def test_an_artifact_with_no_accepted_entry_names_every_missing_field(self):
        # Arrange
        artifact: dict[str, object] = {}

        # Act
        problems = manifest_problems(artifact)

        # Assert
        assert problems == ["id", "title", "filename", "form", "provenance", "accepted"]

    def test_a_malformed_accepted_entry_names_every_bad_value(self):
        # Arrange
        artifact = {
            "id": "x",
            "title": "X",
            "filename": "x.bin",
            "form": "whole file",
            "provenance": "supplied by the developer",
            "accepted": [{"size": 0, "crc32": "zz"}],
        }

        # Act
        problems = manifest_problems(artifact)

        # Assert
        assert problems == ["size", "crc32", "md5", "sha1", "sha256"]

    def test_every_declared_artifact_is_complete(self):
        # Arrange
        manifest = json.loads((ROOT / "artifacts.manifest.json").read_text(encoding="utf-8"))

        # Act
        problems = {entry["id"]: manifest_problems(entry) for entry in manifest["artifacts"]}

        # Assert
        assert problems == {entry["id"]: [] for entry in manifest["artifacts"]}
