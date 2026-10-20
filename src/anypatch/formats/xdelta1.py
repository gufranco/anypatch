from __future__ import annotations

import hashlib
import struct
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from typing import NoReturn

from anypatch.formats import imagesize
from anypatch.formats.apswrite import differing_spans

MAGIC = b"%XDZ004%"
OLDER = {
    b"%XDZ003%": "1.0.4",
    b"%XDZ002%": "1.0",
    b"%XDZ001%": "0.20",
    b"%XDZ000%": "0.18",
    b"%XDELTA%": "0.14",
}
PREFIXES = (b"%XDZ", b"%XDELTA%")
HEADER = struct.Struct(">6I")
WORD = struct.Struct(">I")
PREFIX = len(MAGIC) + HEADER.size
TRAILER = WORD.size + len(MAGIC)
NAME_BITS = 16
NAME_MASK = 0xFFFF
NO_VERIFY = 1
FROM_COMPRESSED = 2
TO_COMPRESSED = 4
PATCH_COMPRESSED = 8
LIBRARY = 3
LIBRARY_BITS = 8
CONTROL_TYPE = (1 << (7 + LIBRARY_BITS)) + LIBRARY
VERSION0_TYPE = (1 << (5 + LIBRARY_BITS)) + LIBRARY
MD5_SIZE = 16
NUMBER_BYTES = 5
NUMBER_LIMIT = 0xFFFFFFFF
GROUP = 0x7F
MORE = 0x80
GZIP = 31
MAX_SOURCES = 2
DATA_NAME = b"(patch data)"
SOURCE_NAME = b"source"
TARGET_NAME = b"target"
LITERAL = -1


class Xdelta1Error(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Source:
    name: bytes
    md5: bytes
    length: int
    isdata: bool
    sequential: bool


@dataclass(frozen=True, slots=True)
class Control:
    to_md5: bytes
    to_len: int
    sources: tuple[Source, ...]
    instructions: tuple[tuple[int, int, int], ...]


class _Cursor:
    __slots__ = ("at", "data")

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.at = 0

    def take(self, size: int) -> bytes:
        if self.at + size > len(self.data):
            raise Xdelta1Error("the control ends early")
        chunk = self.data[self.at : self.at + size]
        self.at += size
        return chunk

    def number(self) -> int:
        value = 0
        for index in range(NUMBER_BYTES):
            byte = self.take(1)[0]
            value |= (byte & GROUP) << (7 * index)
            if not byte & MORE:
                return value if value <= NUMBER_LIMIT else self._too_long()
        return self._too_long()

    def _too_long(self) -> NoReturn:
        raise Xdelta1Error("the control holds a number longer than 32 bits")


def _source(cursor: _Cursor) -> Source:
    name = cursor.take(cursor.number())
    md5 = cursor.take(MD5_SIZE)
    length = cursor.number()
    isdata, sequential = cursor.take(2)
    return Source(name, md5, length, isdata != 0, sequential != 0)


def _instruction(cursor: _Cursor) -> tuple[int, int, int]:
    return cursor.number(), cursor.number(), cursor.number()


def control_of(data: bytes) -> Control:
    cursor = _Cursor(data)
    kind = WORD.unpack(cursor.take(WORD.size))[0]
    cursor.take(WORD.size)
    if kind == VERSION0_TYPE:
        raise Xdelta1Error("an xdelta 1.0 control, which is not read")
    if kind != CONTROL_TYPE:
        raise Xdelta1Error(f"not an xdelta control: type {kind:#x}")
    to_md5 = cursor.take(MD5_SIZE)
    to_len = cursor.number()
    cursor.take(1)
    sources = tuple(_source(cursor) for _ in range(cursor.number()))
    instructions = tuple(_instruction(cursor) for _ in range(cursor.number()))
    return Control(to_md5, to_len, sources, instructions)


def _sections(patch: bytes) -> tuple[int, bytes, bytes]:
    magic = patch[: len(MAGIC)]
    if magic in OLDER:
        version = OLDER[magic]
        raise Xdelta1Error(
            f"an xdelta {version} patch, {magic.decode()}; only xdelta 1.1 patches, "
            f"{MAGIC.decode()}, are read"
        )
    if magic != MAGIC:
        raise Xdelta1Error("not an xdelta 1 patch")
    if len(patch) < PREFIX + TRAILER:
        raise Xdelta1Error("the patch is too short to hold the xdelta 1 header and trailer")
    flags, names = HEADER.unpack_from(patch, len(MAGIC))[:2]
    start = PREFIX + (names >> NAME_BITS) + (names & NAME_MASK)
    if patch[-len(MAGIC) :] != MAGIC:
        raise Xdelta1Error("the trailing magic is damaged")
    control_at = WORD.unpack_from(patch, len(patch) - TRAILER)[0]
    if not start <= control_at <= len(patch) - TRAILER:
        raise Xdelta1Error(f"the control offset {control_at:#x} lies outside the patch")
    return flags, patch[start:control_at], patch[control_at : len(patch) - TRAILER]


def _inflated(section: bytes, limit: int, what: str) -> bytes:
    inflater = zlib.decompressobj(GZIP)
    try:
        out = inflater.decompress(section, limit + 1)
    except zlib.error as error:
        raise Xdelta1Error(f"the compressed {what} is not a gzip stream: {error}") from error
    if len(out) > limit:
        raise Xdelta1Error(f"the {what} inflates past the {limit:,} bytes the patch declares")
    return out


def _data(info: Source, section: bytes, squeezed: bool, source: bytes) -> bytes:
    imagesize.check(info.length, source=len(source))
    return _inflated(section, info.length, "data segment") if squeezed else section


def _origin(info: Source, source: bytes) -> bytes:
    if info.length != len(source):
        raise Xdelta1Error(
            f"made for a {info.length:,}-byte source, but this one is {len(source):,} bytes"
        )
    return source


def _inputs(control: Control, source: bytes, section: bytes, squeezed: bool) -> tuple[bytes, ...]:
    count = len(control.sources)
    if count > MAX_SOURCES:
        raise Xdelta1Error(f"{count} sources; xdelta 1 reads at most a data segment and one source")
    if count == MAX_SOURCES and not control.sources[0].isdata:
        raise Xdelta1Error("two sources where the first is not the data segment")
    return tuple(
        _data(info, section, squeezed, source) if info.isdata else _origin(info, source)
        for info in control.sources
    )


def _spans(control: Control, inputs: tuple[bytes, ...]) -> Iterator[tuple[int, int, int]]:
    positions: dict[int, int] = {}
    for number, (index, offset, length) in enumerate(control.instructions, 1):
        if index >= len(inputs):
            raise Xdelta1Error(
                f"instruction {number} names source {index}, but the patch has {len(inputs)}"
            )
        info = control.sources[index]
        start = positions.get(index, 0) if info.sequential else offset
        positions = {**positions, index: start + length}
        if start + length > len(inputs[index]):
            name = "data segment" if info.isdata else "source"
            raise Xdelta1Error(
                f"instruction {number} copies {length} bytes from {start:#x}, "
                f"past the {len(inputs[index]):,}-byte {name}"
            )
        yield index, start, start + length


def _verified(result: bytes, control: Control, flags: int, source: bytes) -> bytes:
    if flags & NO_VERIFY or hashlib.md5(result, usedforsecurity=False).digest() == control.to_md5:
        return result
    have = hashlib.md5(source, usedforsecurity=False).digest()
    origins = [info.md5 for info in control.sources if not info.isdata]
    if origins and origins[0] != have:
        raise Xdelta1Error(
            f"the source is not the file this patch was made for: MD5 {have.hex()}, "
            f"expected {origins[0].hex()}"
        )
    raise Xdelta1Error("the result does not match the MD5 the patch records")


def apply(source: bytes, patch: bytes) -> bytes:
    flags, section, packed = _sections(patch)
    if flags & (FROM_COMPRESSED | TO_COMPRESSED):
        raise Xdelta1Error(
            "made between gzip-decompressed files, as xdelta 1 does without --pristine; "
            "decompress the source, apply, and compress the result again"
        )
    squeezed = bool(flags & PATCH_COMPRESSED)
    control = control_of(_inflated(packed, imagesize.LIMIT, "control") if squeezed else packed)
    imagesize.check(control.to_len, source=len(source))
    inputs = _inputs(control, source, section, squeezed)
    spans = tuple(_spans(control, inputs))
    total = sum(stop - start for _, start, stop in spans)
    if total != control.to_len:
        raise Xdelta1Error(
            f"the result is {total:,} bytes, but the patch records {control.to_len:,}"
        )
    result = b"".join(inputs[index][start:stop] for index, start, stop in spans)
    return _verified(result, control, flags, source)


def _number(value: int) -> bytes:
    groups = [(value >> (7 * index)) & GROUP for index in range(NUMBER_BYTES)]
    used = max((index + 1 for index, group in enumerate(groups) if group), default=1)
    return bytes(
        group | (MORE if index < used - 1 else 0) for index, group in enumerate(groups[:used])
    )


def _described(name: bytes, data: bytes, *, isdata: bool) -> bytes:
    digest = hashlib.md5(data, usedforsecurity=False).digest()
    return _number(len(name)) + name + digest + _number(len(data)) + bytes([isdata, isdata])


def _operations(before: bytes, after: bytes) -> Iterator[tuple[int, int, bytes]]:
    common = min(len(before), len(after))
    written = 0
    for start, chunk in differing_spans(before[:common], after[:common]):
        if start > written:
            yield written, start - written, b""
        yield LITERAL, len(chunk), chunk
        written = start + len(chunk)
    if common > written:
        yield written, common - written, b""
    if len(after) > common:
        yield LITERAL, len(after) - common, after[common:]


def _control_bytes(before: bytes, after: bytes, operations: list[tuple[int, int, bytes]]) -> bytes:
    data = b"".join(chunk for _, _, chunk in operations)
    origin = 1 if data else 0
    copies = any(at != LITERAL for at, _, _ in operations)
    sources = [_described(DATA_NAME, data, isdata=True)] if data else []
    sources = [*sources, _described(SOURCE_NAME, before, isdata=False)] if copies else sources
    steps = b"".join(
        _number(0 if at == LITERAL else origin) + _number(max(at, 0)) + _number(length)
        for at, length, _ in operations
    )
    digest = hashlib.md5(after, usedforsecurity=False).digest()
    head = WORD.pack(CONTROL_TYPE) + WORD.pack(0) + digest + _number(len(after))
    listed = _number(len(sources)) + b"".join(sources)
    return head + bytes([bool(data)]) + listed + _number(len(operations)) + steps


def build(before: bytes, after: bytes) -> bytes:
    operations = list(_operations(before, after))
    data = b"".join(chunk for _, _, chunk in operations)
    names = len(SOURCE_NAME) << NAME_BITS | len(TARGET_NAME)
    head = MAGIC + HEADER.pack(0, names, 0, 0, 0, 0) + SOURCE_NAME + TARGET_NAME
    control = _control_bytes(before, after, operations)
    return head + data + control + WORD.pack(len(head) + len(data)) + MAGIC
