from __future__ import annotations

import struct
from dataclasses import dataclass

from anypatch.formats import imagesize
from anypatch.formats.apswrite import differing_spans

MAGIC = b"PPF"
VERSIONS = {b"10": 1, b"20": 2, b"30": 3}
DESCRIPTION_AT = 6
DESCRIPTION_LENGTH = 50
RECORDS_AT = DESCRIPTION_AT + DESCRIPTION_LENGTH
BLOCK_LENGTH = 1024
BLOCK_AT = {0: 0x9320, 1: 0x80A0}
MAX_RECORD = 0xFF
DIZ_BEGIN = b"@BEGIN_FILE_ID.DIZ"
DIZ_END = b"@END_FILE_ID.DIZ"
WRITTEN_FLAGS = bytes([0, 0, 1, 0])


class PpfError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Record:
    offset: int
    data: bytes
    undo: bytes | None


@dataclass(frozen=True, slots=True)
class Layout:
    version: int
    undo: bool
    block_at: int | None
    input_size: int | None
    at: int


def _records(before: bytes, after: bytes) -> list[Record]:
    padded = before.ljust(len(after), b"\x00")
    spans = differing_spans(padded, after)
    if len(after) > len(before) and (not spans or spans[-1][0] + len(spans[-1][1]) < len(after)):
        spans = [*spans, (len(after) - 1, after[-1:])]
    pieces = [
        (start + at, data[at : at + MAX_RECORD])
        for start, data in spans
        for at in range(0, len(data), MAX_RECORD)
    ]
    if not pieces and after:
        pieces = [(0, after[:1])]
    return [Record(at, data, padded[at : at + len(data)]) for at, data in pieces]


def build(before: bytes, after: bytes, *, description: str = "") -> bytes:
    if len(after) < len(before):
        raise PpfError("PPF only overwrites and extends, so it cannot shrink a file")
    text = description.encode("ascii", errors="replace")[:DESCRIPTION_LENGTH]
    head = MAGIC + b"30\x02" + text.ljust(DESCRIPTION_LENGTH, b" ") + WRITTEN_FLAGS
    body = b"".join(
        struct.pack("<QB", one.offset, len(one.data)) + one.data + (one.undo or b"")
        for one in _records(before, after)
    )
    return head + body


def _version(patch: bytes) -> int:
    if not patch.startswith(MAGIC):
        raise PpfError("not a PPF patch: it does not start with PPF")
    if len(patch) < RECORDS_AT:
        raise PpfError(f"the patch is {len(patch)} bytes, too short to hold a PPF header")
    version = VERSIONS.get(patch[3:5])
    if version is None or patch[5] != version - 1:
        raise PpfError(f"PPF version {patch[3:6]!r} is not 1, 2 or 3")
    return version


def _layout(patch: bytes) -> Layout:
    version = _version(patch)
    if version == 1:
        return Layout(1, False, None, None, RECORDS_AT)
    if version == 2:
        end = RECORDS_AT + 4 + BLOCK_LENGTH
        if end > len(patch):
            raise PpfError("the patch ends inside its header")
        size = struct.unpack_from("<I", patch, RECORDS_AT)[0]
        return Layout(2, False, BLOCK_AT[0], size, end)
    if len(patch) < RECORDS_AT + 4:
        raise PpfError("the patch ends inside its header")
    kind, blocked, undo = patch[RECORDS_AT : RECORDS_AT + 3]
    block_at = (BLOCK_AT[1] if kind else BLOCK_AT[0]) if blocked else None
    end = RECORDS_AT + 4 + (BLOCK_LENGTH if blocked else 0)
    if end > len(patch):
        raise PpfError("the patch ends inside its header")
    return Layout(3, bool(undo), block_at, None, end)


def _record(patch: bytes, layout: Layout, at: int) -> tuple[Record, int]:
    width = 8 if layout.version == 3 else 4
    if at + width + 1 > len(patch):
        raise PpfError(f"the patch ends inside the record at byte {at}")
    offset = int.from_bytes(patch[at : at + width], "little")
    size = patch[at + width]
    start = at + width + 1
    end = start + size * (2 if layout.undo else 1)
    if end > len(patch):
        raise PpfError(f"the patch ends inside the record at byte {at}")
    undo = patch[start + size : end] if layout.undo else None
    return Record(offset, patch[start : start + size], undo), end


def _parsed(patch: bytes) -> tuple[Layout, list[Record]]:
    layout = _layout(patch)
    records: list[Record] = []
    at = layout.at
    while at < len(patch):
        if patch.startswith(DIZ_BEGIN, at):
            if patch.find(DIZ_END, at) < 0:
                raise PpfError("the FILE_ID.DIZ after the records has no end marker")
            break
        record, at = _record(patch, layout, at)
        records = [*records, record]
    return layout, records


def _checked(source: bytes, patch: bytes, layout: Layout) -> None:
    if layout.input_size is not None and layout.input_size != len(source):
        raise PpfError(
            f"made for a {layout.input_size:,}-byte image, but this one is {len(source):,} bytes"
        )
    if layout.block_at is None:
        return
    held = source[layout.block_at : layout.block_at + BLOCK_LENGTH]
    start = layout.at - BLOCK_LENGTH
    if held != patch[start : start + len(held)]:
        raise PpfError(f"the block check at 0x{layout.block_at:X} does not match this image")


def _verified(out: bytearray, record: Record) -> None:
    held = bytes(out[record.offset : record.offset + len(record.data)])
    if record.undo is None or held in (record.undo, record.data):
        return
    raise PpfError(
        f"at 0x{record.offset:X} this dump holds {held.hex()}, which is neither the original "
        f"{record.undo.hex()} nor the patched {record.data.hex()}"
    )


def apply(before: bytes, patch: bytes) -> bytes:
    layout, records = _parsed(patch)
    _checked(before, patch, layout)
    size = max([len(before), *(one.offset + len(one.data) for one in records)])
    imagesize.check(size, source=len(before))
    out = bytearray(before.ljust(size, b"\x00"))
    for one in records:
        _verified(out, one)
    for one in records:
        out[one.offset : one.offset + len(one.data)] = one.data
    return bytes(out)
