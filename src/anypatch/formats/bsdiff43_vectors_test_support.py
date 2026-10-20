from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass

from anypatch.formats.xdelta_vectors_test_support import edited, moved, text


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    source: bytes
    target: bytes


def cases() -> list[Case]:
    small, wide = text(8000, 41), text(70000, 43)
    return [
        Case("edit", small, edited(small, 51, 12)),
        Case("grow", small, small + text(3000, 52)),
        Case("shrink", small, small[:5000]),
        Case("moved", wide, moved(wide, 53)),
    ]


def _decoded(chunks: tuple[str, ...]) -> bytes:
    return base64.b64decode("".join(chunks))


PATCHES: Mapping[str, bytes] = {
    "edit": _decoded(
        (
            "RU5EU0xFWS9CU0RJRkY0M0AfAAAAAAAAQlpoOTFBWSZTWZFjUqcAAFl//+jZAYCRR0IgQZWhHmMgwNFhSaAdUBAAiEYW",
            "CBSEggAoIAB0KptEaGhkANGhpiAA02kYj1MmGJqEEpoMgyGgDRkNDQ0DCDEGTTCDIfhDwQoF9ILpCCXAwZ9xpdBrBD2J",
            "ZIQEBGcrzkbp0avdHM29vlhMkmtM2tFsrOTuzJQyc3nf0QaCin7RqPq3FR++JhVYEBwB+i+YZIxmKQih6AgKcKKBKfWC",
            "k50wABU/i7kinChISLGpU4A=",
        )
    ),
    "grow": _decoded(
        (
            "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",
        )
    ),
    "shrink": _decoded(
        (
            "RU5EU0xFWS9CU0RJRkY0M4gTAAAAAAAAQlpoOTFBWSZTWTQqwW4AAC9gYOAQCABAQACAAAggADEMCAqUaYlNkLogxeb4",
            "j4u5IpwoSBoVYLcA",
        )
    ),
    "moved": _decoded(
        (
            "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",
        )
    ),
}
