from __future__ import annotations

import struct

from anypatch.formats import imagesize

MAGIC = b"APS10"
TYPE_GENERIC = 0
TYPE_N64 = 1
TYPES = (TYPE_GENERIC, TYPE_N64)
N64_ROM_MAGIC = b"\x80\x37\x12\x40"
ENCODING_SIMPLE = 0
DESCRIPTION_OFFSET = 0x07
DESCRIPTION_LENGTH = 50
FORMAT_OFFSET = 0x39
FORMAT_NATIVE = 1
FORMAT_BYTESWAPPED = 0
ORDERS = (FORMAT_BYTESWAPPED, FORMAT_NATIVE)
CART_OFFSET = 0x3A
COUNTRY_OFFSET = 0x3C
CRC_OFFSET = 0x3D
SIZE_OFFSET = 0x4A
RECORDS_OFFSET = 0x4E
GENERIC_SIZE_OFFSET = 0x39
GENERIC_RECORDS_OFFSET = 0x3D

HEADER_MINIMUM = 0x40
ROM_CRC_OFFSET = 0x10
ROM_CART_OFFSET = 0x3C
ROM_COUNTRY_OFFSET = 0x3E
MAX_RECORD = 0xFF
MIN_RUN = 4
RECORD_HEAD = 5
RUN_MARKER = 0
SCAN_BLOCK = 0x1000
RUN_TAIL = 2


class ApsError(ValueError):
    pass


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
            out += struct.pack("<IBBB", offset + at, RUN_MARKER, chunk[at], run)
            at += run
            continue
        take = min(MAX_RECORD, len(chunk) - at)
        out += struct.pack("<IB", offset + at, take) + chunk[at : at + take]
        at += take
    return bytes(out)


def _generic_header(description: str, size: int) -> bytes:
    text = description.encode("ascii", "replace")[:DESCRIPTION_LENGTH].ljust(DESCRIPTION_LENGTH)
    head = MAGIC + bytes([TYPE_GENERIC, ENCODING_SIMPLE]) + text
    return head + struct.pack("<I", size)


def _header(before: bytes, description: str) -> bytes:
    head = bytearray(RECORDS_OFFSET)
    head[:FORMAT_OFFSET] = _generic_header(description, 0)[:FORMAT_OFFSET]
    head[len(MAGIC)] = TYPE_N64
    head[FORMAT_OFFSET] = FORMAT_NATIVE
    head[CART_OFFSET : CART_OFFSET + 2] = before[ROM_CART_OFFSET : ROM_CART_OFFSET + 2]
    head[COUNTRY_OFFSET] = before[ROM_COUNTRY_OFFSET]
    head[CRC_OFFSET : CRC_OFFSET + 8] = before[ROM_CRC_OFFSET : ROM_CRC_OFFSET + 8]
    struct.pack_into("<I", head, SIZE_OFFSET, len(before))
    return bytes(head)


def _changed(before: bytes, after: bytes) -> list[tuple[int, bytes]]:
    common = min(len(before), len(after))
    tail = after[common:]
    spans = differing_spans(before[:common], after[:common])
    return [*spans, (common, tail)] if tail else spans


def _is_n64_rom(image: bytes) -> bool:
    return len(image) >= HEADER_MINIMUM and image.startswith(N64_ROM_MAGIC)


def _bound_header(before: bytes, after: bytes, description: str) -> bytes:
    head = bytearray(_header(before, description))
    struct.pack_into("<I", head, SIZE_OFFSET, len(after))
    return bytes(head)


def build(
    before: bytes, after: bytes, *, description: str = "", bound: bool | None = None
) -> bytes:
    binds = _is_n64_rom(before) if bound is None else bound
    head = (
        _bound_header(before, after, description)
        if binds
        else _generic_header(description, len(after))
    )
    body = b"".join(_records(offset, chunk) for offset, chunk in _changed(before, after))
    return head + body


def _binding(image: bytes) -> bytes:
    cart = (
        image[ROM_CART_OFFSET : ROM_CART_OFFSET + 2]
        + image[ROM_COUNTRY_OFFSET : ROM_COUNTRY_OFFSET + 1]
    )
    return cart + image[ROM_CRC_OFFSET : ROM_CRC_OFFSET + 8]


def _bound(patch: bytes) -> bytes:
    return patch[CART_OFFSET : CART_OFFSET + 3] + patch[CRC_OFFSET : CRC_OFFSET + 8]


def _described(binding: bytes) -> str:
    crc1, crc2 = struct.unpack_from(">II", binding, 3)
    code = binding[:3].decode("ascii", "replace")
    return f"{code} {crc1:08X} {crc2:08X}"


def _layout(patch: bytes) -> tuple[int, int]:
    if len(patch) < GENERIC_RECORDS_OFFSET or not patch.startswith(MAGIC):
        raise ApsError("not an APS patch: it does not start with an APS10 header")
    kind, encoding = patch[len(MAGIC)], patch[len(MAGIC) + 1]
    if kind not in TYPES:
        raise ApsError(
            f"an APS patch with header type {kind}; only 0, no header, and 1, N64, are read"
        )
    if encoding != ENCODING_SIMPLE:
        raise ApsError(f"an APS patch with encoding {encoding}; only 0, simple, is read")
    if kind == TYPE_GENERIC:
        return GENERIC_SIZE_OFFSET, GENERIC_RECORDS_OFFSET
    if len(patch) < RECORDS_OFFSET:
        raise ApsError("not an APS patch: it ends inside its N64 header")
    return SIZE_OFFSET, RECORDS_OFFSET


def check(before: bytes, patch: bytes) -> None:
    _layout(patch)
    if patch[len(MAGIC)] == TYPE_GENERIC:
        return
    if patch[FORMAT_OFFSET] not in ORDERS:
        raise ApsError(
            f"an APS patch with order byte {patch[FORMAT_OFFSET]}; "
            "only 0, byte-swapped, and 1, native, are read"
        )
    if len(before) < HEADER_MINIMUM or _binding(before) != _bound(patch):
        have = _described(_binding(before)) if len(before) >= HEADER_MINIMUM else "no header"
        raise ApsError(f"bound to {_described(_bound(patch))}, but this dump is {have}")


def _record(patch: bytes, at: int, size: int) -> tuple[int, bytes, int]:
    if at + RECORD_HEAD > len(patch):
        raise ApsError(f"the patch ends inside the record at byte {at}")
    offset, length = struct.unpack_from("<IB", patch, at)
    data_at = at + RECORD_HEAD
    if length == RUN_MARKER:
        if data_at + RUN_TAIL > len(patch):
            raise ApsError(f"the patch ends inside the run record at byte {at}")
        data, end = bytes([patch[data_at]]) * patch[data_at + 1], data_at + RUN_TAIL
    elif data_at + length > len(patch):
        raise ApsError(f"the patch ends inside the {length}-byte record at byte {at}")
    else:
        data, end = patch[data_at : data_at + length], data_at + length
    if offset + len(data) > size:
        raise ApsError(f"a record at {offset:#x} writes past the declared size {size:#x}")
    return offset, data, end


def byteswapped(data: bytes) -> bytes:
    if len(data) % 2:
        raise ApsError(f"a byte-swapped patch needs an even-sized dump, not {len(data):,} bytes")
    out = bytearray(len(data))
    out[0::2] = data[1::2]
    out[1::2] = data[0::2]
    return bytes(out)


def wellformed(patch: bytes) -> bool:
    try:
        size_at, at = _layout(patch)
        size = struct.unpack_from("<I", patch, size_at)[0]
        while at < len(patch):
            at = _record(patch, at, size)[2]
    except ApsError:
        return False
    return True


def apply(before: bytes, patch: bytes) -> bytes:
    check(before, patch)
    size_at, at = _layout(patch)
    swapped = patch[len(MAGIC)] == TYPE_N64 and patch[FORMAT_OFFSET] == FORMAT_BYTESWAPPED
    image = byteswapped(before) if swapped else before
    size = struct.unpack_from("<I", patch, size_at)[0]
    imagesize.check(size, source=len(before))
    out = bytearray(image[:size].ljust(size, b"\x00"))
    while at < len(patch):
        offset, data, at = _record(patch, at, size)
        out[offset : offset + len(data)] = data
    return byteswapped(bytes(out)) if swapped else bytes(out)
