from __future__ import annotations

import struct

from n64_save_patches.apswrite import differing_spans

MAGIC = b"PATCH"
END = b"EOF"
LIMIT = 0x1000000
END_AS_OFFSET = 0x454F46
MAX_RECORD = 0xFFFF
MIN_RUN = 8
RUN_MARKER = 0
OFFSET_BYTES = 3
SIZE_BYTES = 2
RUN_TAIL = 3


class IpsError(ValueError):
    pass


def _offset(value: int) -> bytes:
    return struct.pack(">I", value)[1:]


def _literal(after: bytes, offset: int, size: int) -> bytes:
    if offset == END_AS_OFFSET:
        offset, size = offset - 1, size + 1
    return _offset(offset) + struct.pack(">H", size) + after[offset : offset + size]


def _run(after: bytes, offset: int, size: int) -> bytes:
    if offset == END_AS_OFFSET:
        return _literal(after, offset, size)
    return _offset(offset) + struct.pack(">HHB", RUN_MARKER, size, after[offset])


def _run_length(chunk: bytes, at: int) -> int:
    run = 1
    while at + run < len(chunk) and chunk[at + run] == chunk[at] and run < MAX_RECORD - 1:
        run += 1
    return run


def _records(after: bytes, offset: int, chunk: bytes) -> list[bytes]:
    records: list[bytes] = []
    at = 0
    while at < len(chunk):
        run = _run_length(chunk, at)
        size = run if run >= MIN_RUN else min(MAX_RECORD - 1, len(chunk) - at)
        maker = _run if run >= MIN_RUN else _literal
        records = [*records, maker(after, offset + at, size)]
        at += size
    return records


def build(before: bytes, after: bytes) -> bytes:
    if len(before) != len(after):
        raise ValueError("both images must be the same length to diff them")
    if before[LIMIT:] != after[LIMIT:]:
        raise IpsError(
            "the images differ at or past 16 MiB, where IPS offsets cannot reach; use the APS patch"
        )
    spans = differing_spans(before, after)
    body = b"".join(b"".join(_records(after, offset, chunk)) for offset, chunk in spans)
    return MAGIC + body + END


def apply(before: bytes, patch: bytes) -> bytes:
    if not patch.startswith(MAGIC):
        raise IpsError("not an IPS patch: it does not start with PATCH")
    out = bytearray(before)
    at = len(MAGIC)
    while patch[at : at + len(END)] != END:
        offset = int.from_bytes(patch[at : at + OFFSET_BYTES], "big")
        size = int.from_bytes(patch[at + OFFSET_BYTES : at + OFFSET_BYTES + SIZE_BYTES], "big")
        at += OFFSET_BYTES + SIZE_BYTES
        if size == RUN_MARKER:
            run, value = struct.unpack_from(">HB", patch, at)
            out[offset : offset + run] = bytes([value]) * run
            at += RUN_TAIL
            continue
        out[offset : offset + size] = patch[at : at + size]
        at += size
    return bytes(out)
