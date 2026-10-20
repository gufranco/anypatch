from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass

from anypatch.formats import imagesize
from anypatch.formats.apswrite import differing_spans

MAGIC = b"VPAT"
MD5_MODE = 0x80000000
COUNT_MASK = 0x00FFFFFF
WORD = struct.Struct("<I")
COPY_WIDTHS = {1: struct.Struct("<B"), 2: struct.Struct("<H"), 3: struct.Struct("<I")}
DATA_WIDTHS = {5: struct.Struct("<B"), 6: struct.Struct("<H"), 7: struct.Struct("<I")}
FILETIME = 255
FILETIME_SIZE = 8
BYTE_LIMIT = 1 << 8
WORD_LIMIT = 1 << 16


class VpatchError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Entry:
    number: int
    blocks: int
    source_sum: bytes
    target_sum: bytes
    body: bytes


@dataclass(frozen=True, slots=True)
class Sums:
    name: str
    width: int

    def of(self, data: bytes) -> bytes:
        if self.name == "MD5":
            return hashlib.md5(data, usedforsecurity=False).digest()
        return WORD.pack(zlib.crc32(data))


MD5 = Sums("MD5", 16)
CRC32 = Sums("CRC32", 4)


def _pointed(body: bytes) -> int | None:
    if len(body) < WORD.size:
        return None
    pointer: int = WORD.unpack_from(body, len(body) - WORD.size)[0]
    return pointer if body[pointer : pointer + len(MAGIC)] == MAGIC else None


def _start(patch: bytes) -> int:
    if patch.startswith(MAGIC):
        return 0
    found = _pointed(patch)
    if found is None:
        raise VpatchError("no VPAT header at the start of the file or behind its end pointer")
    return found


def matches(body: bytes) -> bool:
    return body.startswith(MAGIC) or _pointed(body) is not None


def _entry(patch: bytes, at: int, number: int, sums: Sums) -> tuple[Entry, int]:
    head = 2 * WORD.size + 2 * sums.width
    if at + head > len(patch):
        raise VpatchError(f"the patch ends inside the header of patch {number}")
    blocks = WORD.unpack_from(patch, at)[0]
    source_sum = patch[at + WORD.size : at + WORD.size + sums.width]
    target_sum = patch[at + WORD.size + sums.width : at + WORD.size + 2 * sums.width]
    size = WORD.unpack_from(patch, at + head - WORD.size)[0]
    end = at + head + size
    if end > len(patch):
        raise VpatchError(f"the patch ends inside the body of patch {number}")
    return Entry(number, blocks, source_sum, target_sum, patch[at + head : end]), end


def entries(patch: bytes) -> tuple[Sums, list[Entry]]:
    at = _start(patch) + len(MAGIC)
    if at + WORD.size > len(patch):
        raise VpatchError("the patch ends inside the patch count")
    count = WORD.unpack_from(patch, at)[0]
    sums = MD5 if count & MD5_MODE else CRC32
    at += WORD.size
    found: list[Entry] = []
    for number in range(1, (count & COUNT_MASK) + 1):
        one, at = _entry(patch, at, number, sums)
        found = [*found, one]
    return sums, found


def _length(body: bytes, at: int, width: struct.Struct, index: int) -> tuple[int, int]:
    if at + width.size > len(body):
        raise VpatchError(f"the patch ends inside block {index}")
    length: int = width.unpack_from(body, at)[0]
    if length == 0:
        raise VpatchError(f"block {index} is a block of length 0, which VPatch calls corrupt")
    return length, at + width.size


def _copy(source: bytes, body: bytes, at: int, index: int) -> tuple[slice, int]:
    length, at = _length(body, at, COPY_WIDTHS[body[at - 1]], index)
    if at + WORD.size > len(body):
        raise VpatchError(f"the patch ends inside block {index}")
    offset: int = WORD.unpack_from(body, at)[0]
    if offset + length > len(source):
        raise VpatchError(
            f"block {index} copies {length} bytes from {offset:#x}, "
            f"past the {len(source):,}-byte source"
        )
    return slice(offset, offset + length), at + WORD.size


def _literal(body: bytes, at: int, index: int) -> tuple[slice, int]:
    length, at = _length(body, at, DATA_WIDTHS[body[at - 1]], index)
    if at + length > len(body):
        raise VpatchError(f"the patch ends inside block {index}")
    return slice(at, at + length), at + length


def _step(source: bytes, body: bytes, at: int, index: int) -> tuple[bytes | slice, int]:
    if at >= len(body):
        raise VpatchError(f"the patch ends inside block {index}")
    kind = body[at]
    if kind in COPY_WIDTHS:
        return _copy(source, body, at + 1, index)
    if kind in DATA_WIDTHS:
        span, end = _literal(body, at + 1, index)
        return body[span], end
    if kind != FILETIME:
        raise VpatchError(f"unknown block type {kind} in block {index}")
    if at + 1 + FILETIME_SIZE > len(body):
        raise VpatchError(f"the patch ends inside block {index}")
    return b"", at + 1 + FILETIME_SIZE


def _rebuilt(source: bytes, one: Entry) -> bytes:
    pieces: list[bytes | slice] = []
    total = 0
    at = 0
    for index in range(1, one.blocks + 1):
        piece, at = _step(source, one.body, at, index)
        total += len(piece) if isinstance(piece, bytes) else piece.stop - piece.start
        imagesize.check(total, source=len(source))
        pieces = [*pieces, piece]
    return b"".join(source[piece] if isinstance(piece, slice) else piece for piece in pieces)


def apply(source: bytes, patch: bytes) -> bytes:
    sums, found = entries(patch)
    have = sums.of(source)
    chosen = next((one for one in found if one.source_sum == have), None)
    if chosen is None and any(one.target_sum == have for one in found):
        raise VpatchError("this source already is the result of a patch in this file")
    if chosen is None:
        raise VpatchError(f"none of the {len(found)} patches in this file was made for this source")
    result = _rebuilt(source, chosen)
    if sums.of(result) != chosen.target_sum:
        raise VpatchError(f"the result does not match the {sums.name} that patch records")
    return result


def _sized(kinds: tuple[int, int, int], length: int) -> bytes:
    if length < BYTE_LIMIT:
        return bytes([kinds[0], length])
    if length < WORD_LIMIT:
        return bytes([kinds[1]]) + struct.pack("<H", length)
    return bytes([kinds[2]]) + WORD.pack(length)


def _copy_block(offset: int, length: int) -> bytes:
    return _sized((1, 2, 3), length) + WORD.pack(offset)


def _data_block(chunk: bytes) -> bytes:
    return _sized((5, 6, 7), len(chunk)) + chunk


def _blocks(before: bytes, after: bytes) -> list[bytes]:
    common = min(len(before), len(after))
    blocks: list[bytes] = []
    written = 0
    for start, chunk in differing_spans(before[:common], after[:common]):
        if start > written:
            blocks = [*blocks, _copy_block(written, start - written)]
        blocks = [*blocks, _data_block(chunk)]
        written = start + len(chunk)
    if common > written:
        blocks = [*blocks, _copy_block(written, common - written)]
    if len(after) > common:
        blocks = [*blocks, _data_block(after[common:])]
    return blocks


def build(before: bytes, after: bytes) -> bytes:
    blocks = _blocks(before, after)
    body = b"".join(blocks)
    head = WORD.pack(len(blocks)) + MD5.of(before) + MD5.of(after) + WORD.pack(len(body))
    return MAGIC + WORD.pack(1 | MD5_MODE) + head + body
