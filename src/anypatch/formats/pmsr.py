from __future__ import annotations

import struct
import zlib

from anypatch.formats import imagesize
from anypatch.formats.apswrite import differing_spans

MAGIC = b"PMSR"
YAY0 = b"Yay0"
YAY0_HEADER = 0x10
BASE_NAME = "Paper Mario USA 1.0"
BASE_SIZE = 41943040
BASE_CRC = 0xA7F5CD7E
RECORD_HEAD = 8
TOP_BIT = 0x80
DISTANCE = 0xFFF
NIBBLE_BASE = 2
LONG_BASE = 0x12
SHRINKS = "a Star Rod patch only overwrites and extends, so it cannot shrink"


class PmsrError(ValueError):
    pass


class _Yay0:
    def __init__(self, data: bytes) -> None:
        if len(data) < YAY0_HEADER:
            raise PmsrError("the Yay0 header is cut short")
        self.data = data
        self.size, self.link, self.chunk = struct.unpack_from(">III", data, len(YAY0))
        imagesize.check(self.size, source=0)
        self.out = bytearray()

    def literal(self) -> None:
        self.out.append(self.data[self.chunk])
        self.chunk += 1

    def copy(self) -> None:
        pair = struct.unpack_from(">H", self.data, self.link)[0]
        self.link += 2
        count = pair >> 12
        if count == 0:
            count = self.data[self.chunk] + LONG_BASE
            self.chunk += 1
        else:
            count += NIBBLE_BASE
        start = len(self.out) - (pair & DISTANCE) - 1
        if start < 0:
            raise PmsrError(f"a Yay0 copy reaches {-start} bytes before the start of the output")
        period = bytes(self.out[start:])
        self.out.extend((period * -(-count // len(period)))[:count])


def yay0(data: bytes) -> bytes:
    decoder = _Yay0(data)
    bit = 0
    try:
        while len(decoder.out) < decoder.size:
            if data[YAY0_HEADER + bit // 8] & (TOP_BIT >> (bit % 8)):
                decoder.literal()
            else:
                decoder.copy()
            bit += 1
    except (IndexError, struct.error) as error:
        raise PmsrError(f"the Yay0 stream ends before {decoder.size} bytes are decoded") from error
    return bytes(decoder.out[: decoder.size])


def records(patch: bytes) -> list[tuple[int, bytes]]:
    body = yay0(patch) if patch.startswith(YAY0) else patch
    if not body.startswith(MAGIC):
        raise PmsrError("not a Star Rod patch: it does not start with PMSR")
    if len(body) < len(MAGIC) + 4:
        raise PmsrError("the patch ends inside its record count")
    count = struct.unpack_from(">I", body, len(MAGIC))[0]
    found: list[tuple[int, bytes]] = []
    at = len(MAGIC) + 4
    for _ in range(count):
        if at + RECORD_HEAD > len(body):
            raise PmsrError(f"the patch ends inside the record header at byte {at}")
        offset, length = struct.unpack_from(">II", body, at)
        if at + RECORD_HEAD + length > len(body):
            raise PmsrError(f"the patch ends inside the {length}-byte record at byte {at}")
        found = [*found, (offset, body[at + RECORD_HEAD : at + RECORD_HEAD + length])]
        at += RECORD_HEAD + length
    return found


def _bound(before: bytes) -> None:
    crc = zlib.crc32(before)
    if (len(before), crc) != (BASE_SIZE, BASE_CRC):
        raise PmsrError(
            f"made for {BASE_NAME}, {BASE_SIZE:,} bytes with CRC32 {BASE_CRC:08X}; "
            f"this dump is {len(before):,} bytes with CRC32 {crc:08X}"
        )


def build(before: bytes, after: bytes) -> bytes:
    _bound(before)
    if len(after) < len(before):
        raise PmsrError(SHRINKS)
    spans = differing_spans(before, after[: len(before)])
    tail = [(len(before), after[len(before) :])] if len(after) > len(before) else []
    found = [*spans, *tail]
    body = b"".join(struct.pack(">II", at, len(data)) + data for at, data in found)
    return MAGIC + struct.pack(">I", len(found)) + body


def apply(before: bytes, patch: bytes) -> bytes:
    found = records(patch)
    if all(before[at : at + len(data)] == data for at, data in found):
        return before
    _bound(before)
    size = max([len(before), *(at + len(data) for at, data in found)])
    imagesize.check(size, source=len(before))
    out = bytearray(before.ljust(size, b"\x00"))
    for at, data in found:
        out[at : at + len(data)] = data
    return bytes(out)
