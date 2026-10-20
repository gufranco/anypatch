from __future__ import annotations

import re
import struct
import zlib
from dataclasses import dataclass

from anypatch.formats import imagesize, varint
from anypatch.formats.apswrite import differing_spans

MAGIC = b"BPS1"
FOOTER = 12
SELF_CRC = 4
SOURCE_READ = 0
TARGET_READ = 1
SOURCE_COPY = 2
TARGET_COPY = 3
TYPE_BITS = 2
TYPE_MASK = 3
MIN_RUN = 8
RUNS = re.compile(rb"(.)\1{%d,}" % (MIN_RUN - 1), re.DOTALL)


class BpsError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Header:
    source_size: int
    target_size: int
    metadata: bytes
    actions: bytes
    at: int
    source_crc: int
    target_crc: int


def _action(kind: int, length: int) -> bytes:
    return varint.encode(((length - 1) << TYPE_BITS) | kind)


def _signed(value: int) -> bytes:
    return varint.encode((abs(value) << 1) | (value < 0))


def _literal(data: bytes) -> bytes:
    return _action(TARGET_READ, len(data)) + data if data else b""


def _run(at: int, value: int, length: int, copied_to: int) -> bytes:
    head = _action(TARGET_READ, 1) + bytes([value])
    return head + _action(TARGET_COPY, length - 1) + _signed(at - copied_to)


def _target_reads(start: int, chunk: bytes, copied_to: int) -> tuple[bytes, int]:
    pieces: list[bytes] = []
    done = 0
    for found in RUNS.finditer(chunk):
        at = start + found.start()
        pieces = [*pieces, _literal(chunk[done : found.start()])]
        pieces = [*pieces, _run(at, chunk[found.start()], len(found.group()), copied_to)]
        copied_to, done = at + len(found.group()) - 1, found.end()
    return b"".join([*pieces, _literal(chunk[done:])]), copied_to


def _spans(before: bytes, after: bytes) -> list[tuple[int, bytes]]:
    common = min(len(before), len(after))
    spans = differing_spans(before[:common], after[:common])
    return [*spans, (common, after[common:])] if len(after) > common else spans


def _actions(before: bytes, after: bytes) -> bytes:
    pieces: list[bytes] = []
    written = copied_to = 0
    for start, chunk in _spans(before, after):
        same = [_action(SOURCE_READ, start - written)] if start > written else []
        reads, copied_to = _target_reads(start, chunk, copied_to)
        pieces = [*pieces, *same, reads]
        written = start + len(chunk)
    tail = min(len(before), len(after))
    rest = [_action(SOURCE_READ, tail - written)] if tail > written else []
    return b"".join([*pieces, *rest])


def build(before: bytes, after: bytes) -> bytes:
    sizes = varint.encode(len(before)) + varint.encode(len(after)) + varint.encode(0)
    crcs = struct.pack("<II", zlib.crc32(before), zlib.crc32(after))
    body = MAGIC + sizes + _actions(before, after) + crcs
    return body + struct.pack("<I", zlib.crc32(body))


def _checked(patch: bytes) -> None:
    if not patch.startswith(MAGIC):
        raise BpsError("not a BPS patch: it does not start with BPS1")
    if len(patch) < len(MAGIC) + FOOTER:
        raise BpsError(f"the patch is {len(patch)} bytes, too short to hold a BPS header")
    stored = struct.unpack_from("<I", patch, len(patch) - SELF_CRC)[0]
    actual = zlib.crc32(patch[:-SELF_CRC])
    if stored != actual:
        raise BpsError(f"the patch records CRC32 {stored:08X} but is {actual:08X}; it is damaged")


def _header(patch: bytes) -> Header:
    _checked(patch)
    body = patch[: len(patch) - FOOTER]
    try:
        source_size, at = varint.decode(body, len(MAGIC))
        target_size, at = varint.decode(body, at)
        length, at = varint.decode(body, at)
    except varint.VarintError as error:
        raise BpsError(str(error)) from error
    if at + length > len(body):
        raise BpsError(f"the patch ends inside its {length}-byte metadata")
    crcs = struct.unpack_from("<II", patch, len(body))
    return Header(source_size, target_size, body[at : at + length], body, at + length, *crcs)


class _Writer:
    def __init__(self, source: bytes, header: Header) -> None:
        self.source = source
        self.header = header
        imagesize.check(header.target_size, source=len(source))
        self.out = bytearray(header.target_size)
        self.pos = 0
        self.source_at = 0
        self.target_at = 0

    def room(self, length: int) -> None:
        if self.pos + length > len(self.out):
            raise BpsError(f"an action writes past the {len(self.out):,}-byte target")

    def put(self, data: bytes) -> None:
        self.out[self.pos : self.pos + len(data)] = data
        self.pos += len(data)

    def source_read(self, length: int) -> None:
        if self.pos + length > len(self.source):
            raise BpsError(f"a read at 0x{self.pos:X} runs past the end of the source")
        self.put(self.source[self.pos : self.pos + length])

    def source_copy(self, length: int, delta: int) -> None:
        start = self.source_at + delta
        if start < 0 or start + length > len(self.source):
            raise BpsError(f"a copy from 0x{start:X} reaches outside the source")
        self.put(self.source[start : start + length])
        self.source_at = start + length

    def target_copy(self, length: int, delta: int) -> None:
        start = self.target_at + delta
        if start < 0 or start >= self.pos:
            raise BpsError(f"a copy from 0x{start:X} reads target that has not been written")
        period = bytes(self.out[start : self.pos])
        whole = -(-length // len(period))
        self.put((period * whole)[:length] if start + length > self.pos else period[:length])
        self.target_at = start + length


def _step(writer: _Writer, actions: bytes, at: int) -> int:
    word, at = varint.decode(actions, at)
    kind, length = word & TYPE_MASK, (word >> TYPE_BITS) + 1
    writer.room(length)
    if kind == SOURCE_READ:
        writer.source_read(length)
        return at
    if kind == TARGET_READ:
        if at + length > len(actions):
            raise BpsError(f"the patch ends inside the {length}-byte literal at byte {at}")
        writer.put(actions[at : at + length])
        return at + length
    raw, at = varint.decode(actions, at)
    delta = -(raw >> 1) if raw & 1 else raw >> 1
    (writer.source_copy if kind == SOURCE_COPY else writer.target_copy)(length, delta)
    return at


def _forward(source: bytes, header: Header) -> bytes:
    writer = _Writer(source, header)
    at = header.at
    try:
        while at < len(header.actions):
            at = _step(writer, header.actions, at)
    except varint.VarintError as error:
        raise BpsError(str(error)) from error
    if writer.pos != header.target_size:
        raise BpsError(f"the actions write {writer.pos:,} of {header.target_size:,} bytes")
    result = bytes(writer.out)
    if zlib.crc32(result) != header.target_crc:
        raise BpsError(
            f"the result has CRC32 {zlib.crc32(result):08X}; the patch expects "
            f"{header.target_crc:08X}"
        )
    return result


def metadata(patch: bytes) -> str:
    return _header(patch).metadata.decode("utf-8", errors="replace")


def apply(before: bytes, patch: bytes) -> bytes:
    header = _header(patch)
    crc = zlib.crc32(before)
    if (len(before), crc) == (header.source_size, header.source_crc):
        return _forward(before, header)
    if (len(before), crc) == (header.target_size, header.target_crc):
        return before
    raise BpsError(
        f"made for a {header.source_size:,}-byte dump with CRC32 {header.source_crc:08X}, "
        f"but this one is {len(before):,} bytes with CRC32 {crc:08X}"
    )
