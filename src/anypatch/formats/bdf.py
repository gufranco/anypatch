from __future__ import annotations

import bz2
import struct
from dataclasses import dataclass

from n64_save_patches import imagesize

MAGIC = b"BSDIFF40"
HEADER = 32
FIELD = 8
TRIPLE = 3 * FIELD
SIGN = 1 << 63
HIGH = 0x80
LOW = 0x7F


class BdfError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Blocks:
    control: bytes
    diff: bytes
    extra: bytes
    size: int


def _lanes(length: int, value: int) -> int:
    return int.from_bytes(bytes([value]) * length, "big")


def subtract(left: bytes, right: bytes) -> bytes:
    a, b = int.from_bytes(left, "big"), int.from_bytes(right, "big")
    high, low = _lanes(len(left), HIGH), _lanes(len(left), LOW)
    found = ((a | high) - (b & low)) ^ ((a ^ b ^ high) & high)
    return found.to_bytes(len(left), "big")


def add(left: bytes, right: bytes) -> bytes:
    a, b = int.from_bytes(left, "big"), int.from_bytes(right, "big")
    high, low = _lanes(len(left), HIGH), _lanes(len(left), LOW)
    found = ((a & low) + (b & low)) ^ ((a ^ b) & high)
    return found.to_bytes(len(left), "big")


def _offt(value: int) -> bytes:
    return struct.pack("<Q", abs(value) | (SIGN if value < 0 else 0))


def _read_offt(data: bytes, at: int) -> int:
    raw = int.from_bytes(data[at : at + FIELD], "little")
    return -(raw & ~SIGN) if raw & SIGN else raw


def build(before: bytes, after: bytes) -> bytes:
    common = min(len(before), len(after))
    control = bz2.compress(_offt(common) + _offt(len(after) - common) + _offt(0))
    diff = bz2.compress(subtract(after[:common], before[:common]))
    header = MAGIC + _offt(len(control)) + _offt(len(diff)) + _offt(len(after))
    return header + control + diff + bz2.compress(after[common:])


def _blocks(patch: bytes) -> Blocks:
    if not patch.startswith(MAGIC):
        raise BdfError("not a BDF patch: it does not start with BSDIFF40")
    if len(patch) < HEADER:
        raise BdfError(f"the patch is {len(patch)} bytes, too short to hold a BDF header")
    control, diff, size = (_read_offt(patch, at) for at in range(len(MAGIC), HEADER, FIELD))
    if min(control, diff, size) < 0:
        raise BdfError("the header holds a negative length")
    if HEADER + control + diff > len(patch):
        raise BdfError("the patch ends inside its compressed blocks")
    cuts = (HEADER, HEADER + control, HEADER + control + diff, len(patch))
    try:
        control_block, diff_block, extra_block = (
            bz2.decompress(patch[cuts[i] : cuts[i + 1]]) for i in range(3)
        )
    except (OSError, ValueError) as error:
        raise BdfError(f"a bzip2 block does not decompress: {error}") from error
    return Blocks(control_block, diff_block, extra_block, size)


def _window(before: bytes, at: int, length: int) -> bytes:
    start, end = max(at, 0), max(min(at + length, len(before)), 0)
    if start >= end:
        return bytes(length)
    return bytes(start - at) + before[start:end] + bytes(at + length - end)


class _Patcher:
    def __init__(self, before: bytes, blocks: Blocks) -> None:
        self.before = before
        self.blocks = blocks
        imagesize.check(blocks.size, source=len(before))
        self.out = bytearray(blocks.size)
        self.new = self.old = self.diff_at = self.extra_at = 0

    def step(self, adding: int, extra: int, seek: int) -> None:
        if adding < 0 or extra < 0:
            raise BdfError("a control triple holds a negative length")
        if self.new + adding + extra > self.blocks.size:
            raise BdfError(f"a control triple writes past the {self.blocks.size:,}-byte target")
        if self.diff_at + adding > len(self.blocks.diff):
            raise BdfError("a control triple reads past the end of the diff block")
        if self.extra_at + extra > len(self.blocks.extra):
            raise BdfError("a control triple reads past the end of the extra block")
        delta = self.blocks.diff[self.diff_at : self.diff_at + adding]
        self.out[self.new : self.new + adding] = add(delta, _window(self.before, self.old, adding))
        literal = self.blocks.extra[self.extra_at : self.extra_at + extra]
        self.out[self.new + adding : self.new + adding + extra] = literal
        self.new, self.diff_at, self.extra_at = (
            self.new + adding + extra,
            self.diff_at + adding,
            self.extra_at + extra,
        )
        self.old += adding + seek


def apply(before: bytes, patch: bytes) -> bytes:
    blocks = _blocks(patch)
    if len(blocks.control) % TRIPLE:
        raise BdfError(f"the control block is {len(blocks.control)} bytes, not a multiple of 24")
    patcher = _Patcher(before, blocks)
    for at in range(0, len(blocks.control), TRIPLE):
        patcher.step(*(_read_offt(blocks.control, at + k) for k in range(0, TRIPLE, FIELD)))
    if patcher.new != blocks.size:
        raise BdfError(f"the control triples write {patcher.new:,} of {blocks.size:,} bytes")
    return bytes(patcher.out)
