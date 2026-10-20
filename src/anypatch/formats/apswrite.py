from __future__ import annotations

import struct

MAGIC = b"APS10"
TYPE_N64 = 1
ENCODING_SIMPLE = 0
DESCRIPTION_OFFSET = 0x07
DESCRIPTION_LENGTH = 50
FORMAT_OFFSET = 0x39
FORMAT_NATIVE = 1
FORMAT_BYTESWAPPED = 0
CART_OFFSET = 0x3A
COUNTRY_OFFSET = 0x3C
CRC_OFFSET = 0x3D
SIZE_OFFSET = 0x4A
RECORDS_OFFSET = 0x4E

HEADER_MINIMUM = 0x40
ROM_CRC_OFFSET = 0x10
ROM_CART_OFFSET = 0x3C
ROM_COUNTRY_OFFSET = 0x3E
MAX_RECORD = 0xFF
MIN_RUN = 4
RECORD_HEAD = 5
RUN_MARKER = 0
SCAN_BLOCK = 0x1000


def _differing_positions(before: bytes, after: bytes) -> list[int]:
    return [
        at
        for block in range(0, len(before), SCAN_BLOCK)
        if before[block : block + SCAN_BLOCK] != after[block : block + SCAN_BLOCK]
        for at in range(block, min(block + SCAN_BLOCK, len(before)))
        if before[at] != after[at]
    ]


def differing_spans(before: bytes, after: bytes) -> list[tuple[int, bytes]]:
    positions = _differing_positions(before, after)
    last = len(positions) - 1
    starts = [p for i, p in enumerate(positions) if i == 0 or positions[i - 1] != p - 1]
    ends = [p + 1 for i, p in enumerate(positions) if i == last or positions[i + 1] != p + 1]
    return [(start, after[start:end]) for start, end in zip(starts, ends, strict=True)]


def _run_length(chunk: bytes, at: int) -> int:
    run = 1
    while at + run < len(chunk) and chunk[at + run] == chunk[at] and run < MAX_RECORD:
        run += 1
    return run


def _records(offset: int, chunk: bytes) -> bytes:
    out = bytearray()
    at = 0
    while at < len(chunk):
        run = _run_length(chunk, at)
        if run >= MIN_RUN:
            out += struct.pack("<IBBB", offset + at, RUN_MARKER, run, chunk[at])
            at += run
            continue
        take = min(MAX_RECORD, len(chunk) - at)
        out += struct.pack("<IB", offset + at, take) + chunk[at : at + take]
        at += take
    return bytes(out)


def _header(before: bytes, description: str) -> bytes:
    head = bytearray(RECORDS_OFFSET)
    head[0 : len(MAGIC)] = MAGIC
    head[len(MAGIC)] = TYPE_N64
    head[len(MAGIC) + 1] = ENCODING_SIMPLE
    text = description.encode("ascii", "replace")[:DESCRIPTION_LENGTH]
    end = DESCRIPTION_OFFSET + DESCRIPTION_LENGTH
    head[DESCRIPTION_OFFSET:end] = text.ljust(DESCRIPTION_LENGTH)
    head[FORMAT_OFFSET] = FORMAT_NATIVE
    head[CART_OFFSET : CART_OFFSET + 2] = before[ROM_CART_OFFSET : ROM_CART_OFFSET + 2]
    head[COUNTRY_OFFSET] = before[ROM_COUNTRY_OFFSET]
    head[CRC_OFFSET : CRC_OFFSET + 8] = before[ROM_CRC_OFFSET : ROM_CRC_OFFSET + 8]
    struct.pack_into("<I", head, SIZE_OFFSET, len(before))
    return bytes(head)


def build(before: bytes, after: bytes, *, description: str = "") -> bytes:
    if len(before) != len(after):
        raise ValueError("both images must be the same length to diff them")
    if len(before) < HEADER_MINIMUM:
        raise ValueError("too short to carry a ROM header, so nothing can be bound")
    body = b"".join(_records(offset, chunk) for offset, chunk in differing_spans(before, after))
    return _header(before, description) + body


def apply(before: bytes, patch: bytes) -> bytes:
    out = bytearray(before)
    at = RECORDS_OFFSET
    while at + RECORD_HEAD <= len(patch):
        offset, size = struct.unpack_from("<IB", patch, at)
        at += RECORD_HEAD
        if size == RUN_MARKER:
            run, value = patch[at], patch[at + 1]
            at += 2
            out[offset : offset + run] = bytes([value]) * run
            continue
        out[offset : offset + size] = patch[at : at + size]
        at += size
    return bytes(out)
