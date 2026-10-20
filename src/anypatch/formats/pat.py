from __future__ import annotations

import re

from anypatch.formats.apswrite import differing_spans

RECORD = re.compile(rb"^([0-9A-Fa-f]{8}): ([0-9A-Fa-f]{2}) ([0-9A-Fa-f]{2})$")
HEADER = b"Comparing files source and target"
LINE_END = b"\r\n"
LIMIT = 1 << 32


class PatError(ValueError):
    pass


def _text(patch: bytes) -> list[bytes]:
    try:
        patch.decode("ascii")
    except UnicodeDecodeError as error:
        raise PatError("not a PAT patch: it is not text") from error
    return [line.strip() for line in patch.splitlines()]


def _records(patch: bytes) -> list[tuple[int, int, int]]:
    found = [RECORD.match(line) for line in _text(patch)]
    records = [
        (int(one[1], 16), int(one[2], 16), int(one[3], 16)) for one in found if one is not None
    ]
    if not records:
        raise PatError("not a PAT patch: no line reads OOOOOOOO: SS MM")
    return records


def matches(patch: bytes) -> bool:
    try:
        _records(patch)
    except PatError:
        return False
    return True


def record(offset: int, before: int, after: int) -> bytes:
    if offset >= LIMIT:
        raise PatError(f"PAT offsets have 8 hex digits, so {offset:#x} cannot be written")
    return f"{offset:08X}: {before:02X} {after:02X}".encode("ascii") + LINE_END


def build(before: bytes, after: bytes) -> bytes:
    if len(before) != len(after):
        raise PatError("PAT holds only byte changes, so it cannot change a file's size")
    if not before:
        raise PatError("two empty files leave PAT nothing to record")
    lines = [
        record(start + at, before[start + at], value)
        for start, chunk in differing_spans(before, after)
        for at, value in enumerate(chunk)
    ]
    return HEADER + LINE_END + b"".join(lines or [record(0, before[0], before[0])])


def apply(before: bytes, patch: bytes) -> bytes:
    out = bytearray(before)
    for offset, source, target in _records(patch):
        if offset >= len(out):
            raise PatError(f"a record at {offset:#x} lies past the {len(out):,}-byte dump")
        if out[offset] not in (source, target):
            raise PatError(
                f"at {offset:#x} this dump holds {out[offset]:02X}, "
                f"which is neither {source:02X} nor {target:02X}"
            )
        out[offset] = target
    return bytes(out)
