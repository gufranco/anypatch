from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

from n64_save_patches import imagesize, varint
from n64_save_patches.apswrite import differing_spans

MAGIC = b"UPS1"
FOOTER = 12
SELF_CRC = 4
TERMINATOR = b"\x00"


class UpsError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Ups:
    input_size: int
    output_size: int
    hunks: tuple[tuple[int, bytes], ...]
    input_crc: int
    output_crc: int


def xor(left: bytes, right: bytes) -> bytes:
    mixed = int.from_bytes(left, "big") ^ int.from_bytes(right, "big")
    return mixed.to_bytes(len(left), "big")


def _hunks(before: bytes, after: bytes) -> list[bytes]:
    size = max(len(before), len(after))
    padded = before.ljust(size, b"\x00")
    spans = differing_spans(padded, after.ljust(size, b"\x00"))
    ends = [0, *(start + len(data) + 1 for start, data in spans)]
    return [
        varint.encode(start - ends[index]) + xor(padded[start : start + len(data)], data)
        for index, (start, data) in enumerate(spans)
    ]


def build(before: bytes, after: bytes) -> bytes:
    sizes = varint.encode(len(before)) + varint.encode(len(after))
    hunks = b"".join(hunk + TERMINATOR for hunk in _hunks(before, after))
    body = MAGIC + sizes + hunks + struct.pack("<II", zlib.crc32(before), zlib.crc32(after))
    return body + struct.pack("<I", zlib.crc32(body))


def _checked(patch: bytes) -> None:
    if not patch.startswith(MAGIC):
        raise UpsError("not a UPS patch: it does not start with UPS1")
    if len(patch) < len(MAGIC) + FOOTER + 2:
        raise UpsError(f"the patch is {len(patch)} bytes, too short to hold a UPS header")
    stored = struct.unpack_from("<I", patch, len(patch) - SELF_CRC)[0]
    actual = zlib.crc32(patch[:-SELF_CRC])
    if stored != actual:
        raise UpsError(f"the patch records CRC32 {stored:08X} but is {actual:08X}; it is damaged")


def _hunk(body: bytes, at: int, cursor: int) -> tuple[tuple[int, bytes], int]:
    skip, at = varint.decode(body, at)
    stop = body.find(TERMINATOR, at)
    if stop < 0:
        raise UpsError(f"the hunk at byte {at} has no terminator")
    return (cursor + skip, body[at:stop]), stop + 1


def _parsed(patch: bytes) -> Ups:
    _checked(patch)
    body = patch[: len(patch) - FOOTER]
    try:
        input_size, at = varint.decode(body, len(MAGIC))
        output_size, at = varint.decode(body, at)
        hunks: list[tuple[int, bytes]] = []
        cursor = 0
        while at < len(body):
            hunk, at = _hunk(body, at, cursor)
            hunks = [*hunks, hunk]
            cursor = hunk[0] + len(hunk[1]) + 1
    except varint.VarintError as error:
        raise UpsError(str(error)) from error
    crcs = struct.unpack_from("<II", patch, len(body))
    return Ups(input_size, output_size, tuple(hunks), *crcs)


def _forward(before: bytes, found: Ups) -> bytes:
    size = max(found.input_size, found.output_size)
    imagesize.check(size, source=len(before))
    out = bytearray(before.ljust(size, b"\x00"))
    for offset, data in found.hunks:
        if offset + len(data) > size:
            raise UpsError(f"the hunk at 0x{offset:X} runs past the end of a {size:,}-byte image")
        out[offset : offset + len(data)] = xor(bytes(out[offset : offset + len(data)]), data)
    result = bytes(out[: found.output_size])
    if zlib.crc32(result) != found.output_crc:
        raise UpsError(
            f"the result has CRC32 {zlib.crc32(result):08X}; the patch expects "
            f"{found.output_crc:08X}"
        )
    return result


def apply(before: bytes, patch: bytes) -> bytes:
    found = _parsed(patch)
    crc = zlib.crc32(before)
    if (len(before), crc) == (found.input_size, found.input_crc):
        return _forward(before, found)
    if (len(before), crc) == (found.output_size, found.output_crc):
        return before
    raise UpsError(
        f"made for a {found.input_size:,}-byte dump with CRC32 {found.input_crc:08X}, "
        f"but this one is {len(before):,} bytes with CRC32 {crc:08X}"
    )
