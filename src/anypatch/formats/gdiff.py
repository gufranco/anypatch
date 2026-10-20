from __future__ import annotations

import struct
from dataclasses import dataclass

from anypatch.formats import imagesize
from anypatch.formats.apswrite import differing_spans

MAGIC = b"\xd1\xff\xd1\xff"
VERSION = 4
HEADER = len(MAGIC) + 1
EOF = 0
INLINE_LIMIT = 246
DATA_SHORT = 247
DATA_INT = 248
COPY_FORMS = {
    249: ">HB",
    250: ">HH",
    251: ">Hi",
    252: ">iB",
    253: ">iH",
    254: ">ii",
    255: ">qi",
}
USHORT = 0xFFFF
UBYTE = 0xFF
INT = 0x7FFFFFFF


class GdiffError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Copy:
    position: int
    length: int


Operation = Copy | bytes


def copy_command(position: int, length: int) -> bytes:
    if position > INT:
        return bytes([255]) + struct.pack(">qi", position, length)
    short = position <= USHORT
    if length <= UBYTE:
        return bytes([249 if short else 252]) + struct.pack(
            ">HB" if short else ">iB", position, length
        )
    if length <= USHORT:
        return bytes([250 if short else 253]) + struct.pack(
            ">HH" if short else ">iH", position, length
        )
    return bytes([251 if short else 254]) + struct.pack(">Hi" if short else ">ii", position, length)


def copy(position: int, length: int) -> bytes:
    pieces = range(0, length, INT)
    return b"".join(copy_command(position + at, min(INT, length - at)) for at in pieces)


def _data_command(data: bytes) -> bytes:
    if len(data) <= INLINE_LIMIT:
        return bytes([len(data)]) + data
    if len(data) <= USHORT:
        return bytes([DATA_SHORT]) + struct.pack(">H", len(data)) + data
    return bytes([DATA_INT]) + struct.pack(">i", len(data)) + data


def _data(data: bytes) -> bytes:
    return b"".join(_data_command(data[at : at + INT]) for at in range(0, len(data), INT))


def build(before: bytes, after: bytes) -> bytes:
    common = min(len(before), len(after))
    pieces: list[bytes] = []
    written = 0
    for start, chunk in differing_spans(before[:common], after[:common]):
        if start > written:
            pieces = [*pieces, copy(written, start - written)]
        pieces = [*pieces, _data(chunk)]
        written = start + len(chunk)
    if common > written:
        pieces = [*pieces, copy(written, common - written)]
    tail = [_data(after[common:])] if len(after) > common else []
    return MAGIC + bytes([VERSION]) + b"".join([*pieces, *tail]) + bytes([EOF])


def _unpack(patch: bytes, at: int, form: str) -> tuple[int, ...]:
    if at + 1 + struct.calcsize(form) > len(patch):
        raise GdiffError(f"the patch ends inside the command at byte {at}")
    return struct.unpack_from(form, patch, at + 1)


def _literal(patch: bytes, at: int) -> tuple[bytes, int]:
    command = patch[at]
    if command <= INLINE_LIMIT:
        length, start = command, at + 1
    else:
        form = ">H" if command == DATA_SHORT else ">i"
        length, start = _unpack(patch, at, form)[0], at + 1 + struct.calcsize(form)
    if length < 0:
        raise GdiffError(f"the data command at byte {at} carries a negative length")
    if start + length > len(patch):
        raise GdiffError(f"the patch ends inside the {length}-byte data at byte {at}")
    return patch[start : start + length], start + length


def _operation(patch: bytes, at: int, source: int) -> tuple[Operation, int]:
    command = patch[at]
    if command <= DATA_INT:
        return _literal(patch, at)
    form = COPY_FORMS[command]
    position, length = _unpack(patch, at, form)
    if position < 0 or length < 0 or position + length > source:
        raise GdiffError(
            f"a copy of {length} bytes from {position} reaches past the {source:,}-byte source"
        )
    return Copy(position, length), at + 1 + struct.calcsize(form)


def _operations(patch: bytes, source: int) -> list[Operation]:
    if not patch.startswith(MAGIC):
        raise GdiffError("not a GDIFF patch: it does not start with D1 FF D1 FF")
    if len(patch) <= len(MAGIC) or patch[len(MAGIC)] != VERSION:
        version = patch[len(MAGIC)] if len(patch) > len(MAGIC) else "missing"
        raise GdiffError(f"GDIFF version {version}; only version 4 is defined")
    found: list[Operation] = []
    at = HEADER
    while at < len(patch) and patch[at] != EOF:
        operation, at = _operation(patch, at, source)
        found = [*found, operation]
    if at >= len(patch):
        raise GdiffError("the patch ends before its EOF command")
    if at + 1 < len(patch):
        raise GdiffError(f"{len(patch) - at - 1} bytes follow the EOF command")
    return found


def _length(operation: Operation) -> int:
    return operation.length if isinstance(operation, Copy) else len(operation)


def apply(before: bytes, patch: bytes) -> bytes:
    found = _operations(patch, len(before))
    imagesize.check(sum(_length(one) for one in found), source=len(before))
    return b"".join(
        before[one.position : one.position + one.length] if isinstance(one, Copy) else one
        for one in found
    )
