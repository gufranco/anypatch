from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace

from n64_save_patches import imagesize
from n64_save_patches.apswrite import differing_spans
from n64_save_patches.ups import xor

MAGIC = b"NINJA2"
HEADER = 0x800
DESCRIPTION_AT = 0x800 - 1074
DESCRIPTION_LENGTH = 1074
END = 0x00
OPEN_FILE = 0x01
XOR_RECORD = 0x02
ROM_TYPE_RAW = 0
MD5_LENGTH = 16
APPEND = b"A"
MINIFY = b"M"
FLIP = 0xFF
LONGEST_NUMBER = 8


class RupError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Entry:
    source_size: int
    target_size: int
    source_md5: bytes
    target_md5: bytes
    overflow: bytes
    records: tuple[tuple[int, bytes], ...]


def _number(value: int) -> bytes:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "little")
    return bytes([len(raw)]) + raw


def _flipped(data: bytes) -> bytes:
    return xor(data, bytes([FLIP]) * len(data))


def _overflow(before: bytes, after: bytes) -> bytes:
    if len(after) > len(before):
        return APPEND + _number(len(after) - len(before)) + _flipped(after[len(before) :])
    if len(after) < len(before):
        return MINIFY + _number(len(before) - len(after)) + _flipped(before[len(after) :])
    return b""


def _records(before: bytes, after: bytes) -> bytes:
    common = min(len(before), len(after))
    return b"".join(
        bytes([XOR_RECORD])
        + _number(start)
        + _number(len(data))
        + xor(before[start : start + len(data)], data)
        for start, data in differing_spans(before[:common], after[:common])
    )


def build(before: bytes, after: bytes, *, description: str = "") -> bytes:
    text = description.encode("ascii", errors="replace")[:DESCRIPTION_LENGTH]
    head = MAGIC + bytes(DESCRIPTION_AT - len(MAGIC)) + text.ljust(DESCRIPTION_LENGTH, b"\x00")
    sizes = _number(len(before)) + _number(len(after))
    digests = hashlib.md5(before).digest() + hashlib.md5(after).digest()
    entry = bytes([OPEN_FILE]) + _number(0) + bytes([ROM_TYPE_RAW]) + sizes + digests
    return head + entry + _overflow(before, after) + _records(before, after) + bytes([END])


class _Reader:
    def __init__(self, patch: bytes) -> None:
        self.patch = patch
        self.at = HEADER

    def take(self, length: int) -> bytes:
        if self.at + length > len(self.patch):
            raise RupError(f"the patch ends inside a {length}-byte field at byte {self.at}")
        data = self.patch[self.at : self.at + length]
        self.at += length
        return data

    def number(self) -> int:
        width = self.patch[self.at] if self.at < len(self.patch) else 0
        if width > LONGEST_NUMBER:
            raise RupError(f"byte {self.at} starts a number of {width} bytes")
        if self.at + 1 + width > len(self.patch):
            raise RupError(f"the patch ends inside a number at byte {self.at}")
        self.at += 1
        return int.from_bytes(self.take(width), "little")

    def entry(self) -> Entry:
        self.take(self.number())
        self.take(1)
        source_size, target_size = self.number(), self.number()
        source_md5, target_md5 = self.take(MD5_LENGTH), self.take(MD5_LENGTH)
        overflow = b""
        if source_size != target_size:
            mode = self.take(1)
            if mode not in (APPEND, MINIFY):
                raise RupError(f"overflow mode {mode!r} is neither A nor M")
            overflow = _flipped(self.take(self.number()))
        return Entry(source_size, target_size, source_md5, target_md5, overflow, ())


def _with_record(entries: list[Entry], reader: _Reader) -> list[Entry]:
    if not entries:
        raise RupError(f"the XOR record at byte {reader.at - 1} comes before any file")
    offset = reader.number()
    record = (offset, reader.take(reader.number()))
    return [*entries[:-1], replace(entries[-1], records=(*entries[-1].records, record))]


def _entries(patch: bytes) -> list[Entry]:
    if not patch.startswith(MAGIC):
        raise RupError("not a RUP patch: it does not start with NINJA2")
    if len(patch) < HEADER:
        raise RupError(f"the patch is {len(patch)} bytes, too short to hold a RUP header")
    reader = _Reader(patch)
    entries: list[Entry] = []
    while reader.at < len(patch):
        command = reader.take(1)[0]
        if command == END:
            return entries
        if command == OPEN_FILE:
            entries = [*entries, reader.entry()]
        elif command == XOR_RECORD:
            entries = _with_record(entries, reader)
        else:
            raise RupError(f"unknown command 0x{command:02X} at byte {reader.at - 1}")
    raise RupError("the patch has no end command")


def _forward(before: bytes, entry: Entry) -> bytes:
    imagesize.check(entry.target_size, source=len(before))
    out = bytearray(before[: entry.target_size].ljust(entry.target_size, b"\x00"))
    for offset, data in entry.records:
        if offset + len(data) > entry.target_size:
            raise RupError(
                f"the record at 0x{offset:X} runs past the {entry.target_size:,}-byte target"
            )
        held = before[offset : offset + len(data)].ljust(len(data), b"\x00")
        out[offset : offset + len(data)] = xor(held, data)
    if entry.target_size > entry.source_size:
        out[entry.source_size :] = entry.overflow
    result = bytes(out[: entry.target_size])
    if hashlib.md5(result).digest() != entry.target_md5:
        raise RupError(
            f"the result has MD5 {hashlib.md5(result).hexdigest()}; the patch expects "
            f"{entry.target_md5.hex()}"
        )
    return result


def apply(before: bytes, patch: bytes) -> bytes:
    entries = _entries(patch)
    digest = hashlib.md5(before).digest()
    for entry in entries:
        if entry.source_md5 == digest:
            return _forward(before, entry)
    if any(entry.target_md5 == digest for entry in entries):
        return before
    wanted = ", ".join(entry.source_md5.hex() for entry in entries)
    raise RupError(f"made for MD5 {wanted}, but this dump is {digest.hex()}")
