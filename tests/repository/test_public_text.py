from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def tagline() -> str:
    found = re.search(r"<strong>(.+?)</strong>", (ROOT / "README.md").read_text(encoding="utf-8"))
    assert found is not None
    return found.group(1)


class TestTheReadmeIsTheSource:
    def test_the_package_description_is_the_tagline(self):
        # Arrange
        manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        # Act
        description = manifest["project"]["description"]

        # Assert
        assert description == tagline()

    def test_the_citation_abstract_is_the_tagline(self):
        # Arrange
        text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")

        # Act
        found = re.search(r"^abstract: (.+)$", text, re.MULTILINE)

        # Assert
        assert found is not None
        assert found.group(1) == tagline()

    def test_every_translation_links_back_to_the_others(self):
        # Arrange
        names = ["README.md", "README.ja.md", "README.zh-Hans.md", "README.zh-HK.md"]

        # Act
        texts = {name: (ROOT / name).read_text(encoding="utf-8") for name in names}

        # Assert
        for name, text in texts.items():
            others = [other for other in names if other != name]
            assert all(f"({other})" in text for other in others), name
