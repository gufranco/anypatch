from __future__ import annotations

import json
import struct
from collections.abc import Mapping
from dataclasses import dataclass

from n64_save_patches import imagesize
from n64_save_patches.apswrite import differing_spans

MAGIC = b"PATCH"
END = b"EOF"
MAGIC32 = b"IPS32"
END32 = b"EEOF"
LIMIT = 0x1000000
LIMIT32 = 0x100000000
END_AS_OFFSET = 0x454F46
MAX_RECORD = 0xFFFF
MIN_RUN = 8
RUN_MARKER = 0
OFFSET_BYTES = 3
SIZE_BYTES = 2
RUN_TAIL = 3
EBP_PATCHER = "EBPatcher"


class IpsError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Variant:
    name: str
    magic: bytes
    end: bytes
    width: int
    limit: int

    @property
    def end_as_offset(self) -> int:
        return int.from_bytes(self.end, "big")


IPS = Variant("IPS", MAGIC, END, OFFSET_BYTES, LIMIT)
IPS32 = Variant("IPS32", MAGIC32, END32, 4, LIMIT32)


def _offset(variant: Variant, value: int) -> bytes:
    return value.to_bytes(variant.width, "big")


def _literal(variant: Variant, after: bytes, offset: int, size: int) -> bytes:
    if offset == variant.end_as_offset:
        offset, size = offset - 1, size + 1
    return _offset(variant, offset) + struct.pack(">H", size) + after[offset : offset + size]


def _run(variant: Variant, after: bytes, offset: int, size: int) -> bytes:
    if offset == variant.end_as_offset:
        return _literal(variant, after, offset, size)
    return _offset(variant, offset) + struct.pack(">HHB", RUN_MARKER, size, after[offset])


def _run_length(chunk: bytes, at: int) -> int:
    run = 1
    while at + run < len(chunk) and chunk[at + run] == chunk[at] and run < MAX_RECORD - 1:
        run += 1
    return run


def _records(variant: Variant, after: bytes, offset: int, chunk: bytes) -> list[bytes]:
    records: list[bytes] = []
    at = 0
    while at < len(chunk):
        run = _run_length(chunk, at)
        size = run if run >= MIN_RUN else min(MAX_RECORD - 1, len(chunk) - at)
        maker = _run if run >= MIN_RUN else _literal
        records = [*records, maker(variant, after, offset + at, size)]
        at += size
    return records


def _changed(before: bytes, after: bytes) -> list[tuple[int, bytes]]:
    common = min(len(before), len(after))
    spans = differing_spans(before[:common], after[:common])
    tail = after[common:]
    return [*spans, (common, tail)] if tail else spans


def _body(variant: Variant, before: bytes, after: bytes) -> bytes:
    spans = _changed(before, after)
    return b"".join(b"".join(_records(variant, after, offset, chunk)) for offset, chunk in spans)


def fits(before: bytes, after: bytes) -> bool:
    return len(after) <= LIMIT and before[LIMIT : len(after)] == after[LIMIT:]


def build_variant(variant: Variant, before: bytes, after: bytes) -> bytes:
    if len(after) > variant.limit:
        raise IpsError(f"{variant.name} offsets cannot reach a {len(after):,}-byte image")
    shorter = _offset(variant, len(after)) if len(after) < len(before) else b""
    return variant.magic + _body(variant, before, after) + variant.end + shorter


def build(before: bytes, after: bytes) -> bytes:
    return build_variant(IPS if fits(before, after) else IPS32, before, after)


def build_ebp(before: bytes, after: bytes, metadata: Mapping[str, str]) -> bytes:
    if not fits(before, after):
        raise IpsError("EBP is IPS, so it cannot reach past 16 MiB; use IPS32, APS or xdelta")
    if len(after) < len(before):
        raise IpsError("EBP carries metadata where IPS keeps a size, so it cannot shrink a file")
    text = json.dumps({"patcher": EBP_PATCHER, **metadata}).encode("utf-8")
    return MAGIC + _body(IPS, before, after) + END + text


def _header(variant: Variant, patch: bytes, at: int) -> tuple[int, int]:
    if at + variant.width + SIZE_BYTES > len(patch):
        raise IpsError(f"the patch ends inside the record at byte {at}")
    offset = int.from_bytes(patch[at : at + variant.width], "big")
    size = int.from_bytes(patch[at + variant.width : at + variant.width + SIZE_BYTES], "big")
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


def _sized(variant: Variant, out: bytes, tail: bytes) -> bytes:
    if not tail:
        return out
    if len(tail) == variant.width:
        return out[: int.from_bytes(tail, "big")]
    if variant is IPS and tail.startswith(b"{"):
        _metadata(tail)
        return out
    raise IpsError(
        f"{len(tail)} bytes follow {variant.end.decode()}, which are neither a size "
        "nor EBP metadata"
    )


def _metadata(tail: bytes) -> dict[str, object]:
    try:
        found = json.loads(tail.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IpsError(f"the EBP metadata after EOF is not JSON: {error}") from error
    return dict(found)


def variant_of(patch: bytes) -> Variant:
    if patch.startswith(MAGIC32):
        return IPS32
    if patch.startswith(MAGIC):
        return IPS
    raise IpsError("not an IPS patch: it does not start with PATCH or IPS32")


def _parsed(patch: bytes) -> tuple[Variant, list[tuple[int, bytes]], bytes]:
    variant = variant_of(patch)
    records: list[tuple[int, bytes]] = []
    at = len(variant.magic)
    while patch[at : at + len(variant.end)] != variant.end:
        offset, size = _header(variant, patch, at)
        data, at = _payload(patch, at + variant.width + SIZE_BYTES, size)
        records = [*records, (offset, data)]
    return variant, records, patch[at + len(variant.end) :]


def metadata(patch: bytes) -> dict[str, object] | None:
    variant, _, tail = _parsed(patch)
    if variant is IPS and tail.startswith(b"{"):
        return _metadata(tail)
    return None


def apply(before: bytes, patch: bytes) -> bytes:
    variant, records, tail = _parsed(patch)
    imagesize.check(
        max([len(before), *(offset + len(data) for offset, data in records)]),
        source=len(before),
    )
    out = bytearray(before)
    for offset, data in records:
        if offset > len(out):
            out.extend(bytes(offset - len(out)))
        out[offset : offset + len(data)] = data
    return _sized(variant, bytes(out), tail)
