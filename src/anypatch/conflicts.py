from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from anypatch.formats.apswrite import differing_spans

INPUT = "the input"
SHOWN = 16

Span = tuple[int, bytes]
Range = tuple[int, int]


@dataclass(frozen=True, slots=True)
class Change:
    name: str
    spans: tuple[Span, ...]
    size: int


@dataclass(frozen=True, slots=True)
class Conflict:
    first: str
    second: str
    start: int
    end: int
    first_bytes: bytes
    second_bytes: bytes

    def describe(self) -> str:
        shown = (self.first_bytes[:SHOWN].hex(), self.second_bytes[:SHOWN].hex())
        where = f"0x{self.start:06X}..0x{self.end:06X}"
        return f"{where}: {self.first} writes {shown[0]}, {self.second} writes {shown[1]}"


class ConflictError(ValueError):
    def __init__(self, found: Sequence[Conflict], sizes: Sequence[tuple[str, int]]) -> None:
        self.conflicts = tuple(found)
        self.sizes = tuple(sizes)
        lines = [one.describe() for one in self.conflicts]
        lines += [f"{name} makes it {size:#x} bytes" for name, size in self.sizes]
        super().__init__("the patches conflict:\n  " + "\n  ".join(lines))


@dataclass(frozen=True, slots=True)
class Merged:
    image: bytes
    applied: tuple[str, ...]
    already: tuple[str, ...]


def change(name: str, base: bytes, result: bytes) -> Change:
    common = min(len(base), len(result))
    spans = differing_spans(base[:common], result[:common])
    tail = result[common:]
    return Change(name, tuple([*spans, (common, tail)] if tail else spans), len(result))


def _end(span: Span) -> int:
    return span[0] + len(span[1])


def _outside(start: int, end: int, ignore: Sequence[Range]) -> list[Range]:
    pieces = [(start, end)]
    for low, high in ignore:
        pieces = [
            piece
            for a, b in pieces
            for piece in ((a, min(b, low)), (max(a, high), b))
            if piece[0] < piece[1]
        ]
    return pieces


def _differences(a: Span, b: Span, start: int, end: int) -> list[Range]:
    left = a[1][start - a[0] : end - a[0]]
    right = b[1][start - b[0] : end - b[0]]
    return [(start + s, start + s + len(chunk)) for s, chunk in differing_spans(left, right)]


def _found(
    pair: tuple[Change, Change], a: Span, b: Span, ignore: Sequence[Range]
) -> list[Conflict]:
    start, end = max(a[0], b[0]), min(_end(a), _end(b))
    return [
        Conflict(
            pair[0].name,
            pair[1].name,
            lo,
            hi,
            a[1][lo - a[0] : hi - a[0]],
            b[1][lo - b[0] : hi - b[0]],
        )
        for piece in _outside(start, end, ignore)
        for lo, hi in _differences(a, b, *piece)
    ]


def _pair(first: Change, second: Change, ignore: Sequence[Range]) -> list[Conflict]:
    found: list[Conflict] = []
    i = j = 0
    while i < len(first.spans) and j < len(second.spans):
        a, b = first.spans[i], second.spans[j]
        if max(a[0], b[0]) < min(_end(a), _end(b)):
            found = [*found, *_found((first, second), a, b, ignore)]
        if _end(a) <= _end(b):
            i += 1
        else:
            j += 1
    return found


def conflicts(changes: Sequence[Change], *, ignore: Sequence[Range] = ()) -> list[Conflict]:
    return [
        found
        for index, first in enumerate(changes)
        for second in changes[index + 1 :]
        for found in _pair(first, second, ignore)
    ]


def _final_size(changes: Sequence[Change], base: int) -> int:
    return next((one.size for one in changes if one.size != base), base)


def _sizes(changes: Sequence[Change], base: int) -> list[tuple[str, int]]:
    resized = [(one.name, one.size) for one in changes if one.size != base]
    final = _final_size(changes, base)
    beyond = [(one.name, one.size) for one in changes if one.spans and _end(one.spans[-1]) > final]
    if len({size for _, size in resized}) > 1 or beyond:
        return [*resized, *(entry for entry in beyond if entry not in resized)]
    return []


def _compared(one: Change, ignore: Sequence[Range]) -> list[tuple[int, int, int, bytes]]:
    pieces = [
        (lo, hi, start, data)
        for start, data in one.spans
        for lo, hi in _outside(start, start + len(data), ignore)
    ]
    whole = [(start, start + len(data), start, data) for start, data in one.spans]
    return pieces or whole


def _carried(one: Change, image: bytes, ignore: Sequence[Range]) -> bool:
    if one.size != len(image):
        return False
    return all(
        image[lo:hi] == data[lo - start : hi - start]
        for lo, hi, start, data in _compared(one, ignore)
    )


def compose(base: bytes, changes: Sequence[Change]) -> bytes:
    size = _final_size(changes, len(base))
    out = bytearray(base[:size].ljust(size, b"\x00"))
    for one in changes:
        for start, data in one.spans:
            out[start : start + len(data)] = data
    return bytes(out)


def merge(
    image: bytes, clean: bytes, changes: Sequence[Change], *, ignore: Sequence[Range] = ()
) -> Merged:
    already = [one for one in changes if _carried(one, image, ignore)]
    fresh = [one for one in changes if one not in already]
    carried = change(INPUT, clean, image) if image != clean else None
    participants = [*([carried] if carried else []), *fresh]
    found, sizes = conflicts(participants, ignore=ignore), _sizes(participants, len(clean))
    if found or sizes:
        raise ConflictError(found, sizes)
    return Merged(
        compose(clean, participants),
        tuple(one.name for one in fresh),
        tuple(one.name for one in already),
    )
