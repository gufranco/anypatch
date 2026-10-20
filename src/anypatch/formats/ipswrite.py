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


def _changed(before: bytes, after: bytes) -> list[tuple[int, bytes]]:
    common = min(len(before), len(after))
    spans = differing_spans(before[:common], after[:common])
    tail = after[common:]
    return [*spans, (common, tail)] if tail else spans


def build(before: bytes, after: bytes) -> bytes:
    if len(after) > LIMIT or before[LIMIT : len(after)] != after[LIMIT:]:
        raise IpsError(
            "the images differ at or past 16 MiB, where IPS offsets cannot reach; use APS or xdelta"
        )
    spans = _changed(before, after)
    body = b"".join(b"".join(_records(after, offset, chunk)) for offset, chunk in spans)
    shorter = _offset(len(after)) if len(after) < len(before) else b""
    return MAGIC + body + END + shorter


def _header(patch: bytes, at: int) -> tuple[int, int]:
    if at + OFFSET_BYTES + SIZE_BYTES > len(patch):
        raise IpsError(f"the patch ends inside the record at byte {at}")
    offset = int.from_bytes(patch[at : at + OFFSET_BYTES], "big")
    size = int.from_bytes(patch[at + OFFSET_BYTES : at + OFFSET_BYTES + SIZE_BYTES], "big")
    return offset, size


def _payload(patch: bytes, at: int, size: int) -> tuple[bytes, int]:
    if size == RUN_MARKER:
        if at + RUN_TAIL > len(patch):
            raise IpsError(f"the patch ends inside the run record at byte {at}")
        run, value = struct.unpack_from(">HB", patch, at)
        return bytes([value]) * run, at + RUN_TAIL
    if at + size > len(patch):
        raise IpsError(f"the patch ends inside the {size}-byte record at byte {at}")
    return patch[at : at + size], at + size


def _sized(out: bytes, tail: bytes) -> bytes:
    if not tail:
        return out
    if len(tail) != OFFSET_BYTES:
        raise IpsError(f"{len(tail)} bytes follow EOF, which is neither nothing nor a 3-byte size")
    return out[: int.from_bytes(tail, "big")]


def _parsed(patch: bytes) -> tuple[list[tuple[int, bytes]], bytes]:
    if not patch.startswith(MAGIC):
        raise IpsError("not an IPS patch: it does not start with PATCH")
    records: list[tuple[int, bytes]] = []
    at = len(MAGIC)
    while patch[at : at + len(END)] != END:
        offset, size = _header(patch, at)
        data, at = _payload(patch, at + OFFSET_BYTES + SIZE_BYTES, size)
        records = [*records, (offset, data)]
    return records, patch[at + len(END) :]


def apply(before: bytes, patch: bytes) -> bytes:
    records, tail = _parsed(patch)
    out = bytearray(before)
    for offset, data in records:
        if offset > len(out):
            out.extend(bytes(offset - len(out)))
        out[offset : offset + len(data)] = data
    return _sized(bytes(out), tail)
