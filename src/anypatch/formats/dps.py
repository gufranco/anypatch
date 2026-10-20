from __future__ import annotations

import struct

from anypatch.formats import imagesize
from anypatch.formats.apswrite import differing_spans

FIELD = 64
FLAG_AT = 3 * FIELD
VERSION_AT = FLAG_AT + 1
SIZE_AT = VERSION_AT + 1
HEADER = SIZE_AT + 4
VERSION = 1
COPY, DATA = 0, 1
COPY_RECORD = struct.Struct("<BIII")
DATA_RECORD = struct.Struct("<BII")


class DpsError(ValueError):
    pass


def _header(before: bytes, description: str) -> bytes:
    name = description.encode("ascii", "replace")[:FIELD].ljust(FIELD, b"\x00")
    return name + bytes(2 * FIELD) + bytes([0, VERSION]) + struct.pack("<I", len(before))


def _pieces(before: bytes, after: bytes) -> list[bytes]:
    common = min(len(before), len(after))
    pieces: list[bytes] = []
    written = 0
    for start, chunk in differing_spans(before[:common], after[:common]):
        if start > written:
            pieces = [*pieces, COPY_RECORD.pack(COPY, written, written, start - written)]
        pieces = [*pieces, DATA_RECORD.pack(DATA, start, len(chunk)) + chunk]
        written = start + len(chunk)
    if common > written:
        pieces = [*pieces, COPY_RECORD.pack(COPY, written, written, common - written)]
    if len(after) > common:
        tail = after[common:]
        pieces = [*pieces, DATA_RECORD.pack(DATA, common, len(tail)) + tail]
    return pieces


def build(before: bytes, after: bytes, *, description: str = "") -> bytes:
    return _header(before, description) + b"".join(_pieces(before, after))


def _checked_header(before: bytes, patch: bytes) -> None:
    if len(patch) < HEADER:
        raise DpsError(f"the patch is too short to hold the {HEADER}-byte DPS header")
    if patch[VERSION_AT] != VERSION:
        raise DpsError(f"DPS version {patch[VERSION_AT]}; only {VERSION} is read")
    size = struct.unpack_from("<I", patch, SIZE_AT)[0]
    if size != len(before):
        raise DpsError(f"made for a {size:,}-byte source, but this one is {len(before):,} bytes")


def _record(before: bytes, patch: bytes, at: int) -> tuple[int, bytes, int]:
    mode = patch[at]
    if mode not in (COPY, DATA):
        raise DpsError(f"unknown record mode {mode} at byte {at}")
    shape = COPY_RECORD if mode == COPY else DATA_RECORD
    if at + shape.size > len(patch):
        raise DpsError(f"the patch ends inside the record at byte {at}")
    if mode == DATA:
        _, out_at, length = DATA_RECORD.unpack_from(patch, at)
        end = at + DATA_RECORD.size + length
        if end > len(patch):
            raise DpsError(f"the patch ends inside the record at byte {at}")
        return out_at, patch[at + DATA_RECORD.size : end], end
    _, out_at, in_at, length = COPY_RECORD.unpack_from(patch, at)
    if in_at + length > len(before):
        raise DpsError(
            f"a record copies {length} bytes from {in_at:#x}, past the {len(before):,}-byte source"
        )
    return out_at, before[in_at : in_at + length], at + COPY_RECORD.size


def apply(before: bytes, patch: bytes) -> bytes:
    _checked_header(before, patch)
    found: list[tuple[int, bytes]] = []
    at = HEADER
    while at < len(patch):
        out_at, piece, at = _record(before, patch, at)
        imagesize.check(out_at + len(piece), source=len(before))
        found = [*found, (out_at, piece)]
    size = max([0, *(out_at + len(piece) for out_at, piece in found)])
    out = bytearray(size)
    for out_at, piece in found:
        out[out_at : out_at + len(piece)] = piece
    return bytes(out)
