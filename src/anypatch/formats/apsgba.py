from __future__ import annotations

import binascii
import struct
from dataclasses import dataclass

from anypatch.formats import imagesize
from anypatch.formats.ups import xor

MAGIC = b"APS1"
N64_MAGIC = b"APS10"
HEADER = 12
BLOCK = 0x10000
RECORD_HEAD = 8
RECORD = RECORD_HEAD + BLOCK
CRC16_START = 0xFFFF
IDENTICAL = "the files are identical, and an APS for GBA patch needs a record"


class ApsGbaError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Record:
    offset: int
    source_crc: int
    target_crc: int
    xor: bytes


def crc16(data: bytes) -> int:
    return binascii.crc_hqx(data, CRC16_START)


def matches(patch: bytes) -> bool:
    shaped = len(patch) >= HEADER + RECORD and (len(patch) - HEADER) % RECORD == 0
    return patch.startswith(MAGIC) and not patch.startswith(N64_MAGIC) and shaped


def _record(patch: bytes, at: int) -> Record:
    offset, source_crc, target_crc = struct.unpack_from("<IHH", patch, at)
    return Record(offset, source_crc, target_crc, patch[at + RECORD_HEAD : at + RECORD])


def _parsed(patch: bytes) -> tuple[int, int, list[Record]]:
    if not matches(patch):
        raise ApsGbaError("not a GBA APS patch: APS1, two sizes, then 65,544-byte records")
    sizes = struct.unpack_from("<II", patch, len(MAGIC))
    records = [_record(patch, at) for at in range(HEADER, len(patch), RECORD)]
    return sizes[0], sizes[1], records


def _block(data: bytes | bytearray, at: int) -> bytes:
    return bytes(data[at : at + BLOCK]).ljust(BLOCK, b"\x00")


def _carried(before: bytes, target_size: int, records: list[Record]) -> bool:
    return len(before) == target_size and all(
        crc16(_block(before, one.offset)) == one.target_crc for one in records
    )


def _patched(before: bytes, one: Record) -> bytes:
    original = _block(before, one.offset)
    if crc16(original) != one.source_crc:
        raise ApsGbaError(
            f"the block at 0x{one.offset:X} has CRC16 {crc16(original):04X}; "
            f"the patch expects {one.source_crc:04X}"
        )
    result = xor(original, one.xor)
    if crc16(result) != one.target_crc:
        raise ApsGbaError(
            f"the patched block at 0x{one.offset:X} has CRC16 {crc16(result):04X}; "
            f"the patch expects {one.target_crc:04X}"
        )
    return result


def apply(before: bytes, patch: bytes) -> bytes:
    source_size, target_size, records = _parsed(patch)
    if _carried(before, target_size, records):
        return before
    if len(before) != source_size:
        raise ApsGbaError(
            f"made for a {source_size:,}-byte dump, but this one is {len(before):,} bytes"
        )
    size = max([target_size, *(one.offset + BLOCK for one in records)])
    imagesize.check(size, source=len(before))
    out = bytearray(before.ljust(size, b"\x00"))
    for one in records:
        out[one.offset : one.offset + BLOCK] = _patched(before, one)
    return bytes(out[:target_size])


def _written(before: bytes, after: bytes, at: int) -> bytes:
    source, target = _block(before, at), _block(after, at)
    head = struct.pack("<IHH", at, crc16(source), crc16(target))
    return head + xor(source, target)


def build(before: bytes, after: bytes) -> bytes:
    span = max(len(before), len(after))
    changed = [at for at in range(0, span, BLOCK) if _block(before, at) != _block(after, at)]
    if not changed:
        raise ApsGbaError(IDENTICAL)
    sizes = struct.pack("<II", len(before), len(after))
    return MAGIC + sizes + b"".join(_written(before, after, at) for at in changed)
