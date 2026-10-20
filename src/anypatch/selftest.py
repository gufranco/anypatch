from __future__ import annotations

import binascii
import struct
from collections.abc import Callable

from anypatch import api
from anypatch.doctor import Check, CheckStatus
from anypatch.formats import apsgba, pmsr
from anypatch.patchio import WRITABLE, Format

N64_MAGIC = b"\x80\x37\x12\x40"
BASE = N64_MAGIC + bytes((at * 7) & 0xFF for at in range(4, 0x400))
AFTER = BASE[:0x200] + b"\xde\xad\xbe\xef" + BASE[0x204:] + b"tail"
GBA_BLOCK = 0x10000
GBA_SOURCE = bytes(range(256)) * (GBA_BLOCK // 256)
GBA_TARGET = b"\x01" + GBA_SOURCE[1:]
STAR_ROD_RECORD = (0x10, b"star")
DIFFERS = "a patch it wrote did not replay to its target"

Probe = Callable[[Format], bool]


def _round_trip(kind: Format) -> bool:
    files = api.make(BASE, AFTER, kind)
    name = f"selftest.{kind.value}"
    patch = api.load(files[f".{kind.value}"], name=name, binding=files.get(".hdr"))
    return api.apply(BASE, [patch]).image == AFTER


def _crc16(data: bytes) -> int:
    return binascii.crc_hqx(data, 0xFFFF)


def _gba() -> bool:
    record = struct.pack("<IHH", 0, _crc16(GBA_SOURCE), _crc16(GBA_TARGET))
    xor = bytes(a ^ b for a, b in zip(GBA_SOURCE, GBA_TARGET, strict=True))
    patch = apsgba.MAGIC + struct.pack("<II", GBA_BLOCK, GBA_BLOCK) + record + xor
    return apsgba.apply(GBA_SOURCE, patch) == GBA_TARGET


def _star_rod() -> bool:
    offset, data = STAR_ROD_RECORD
    patch = pmsr.MAGIC + struct.pack(">III", 1, offset, len(data)) + data
    return pmsr.records(patch) == [STAR_ROD_RECORD]


def _probe(kind: Format) -> bool:
    if kind is Format.APS_GBA:
        return _gba()
    if kind is Format.PMSR:
        return _star_rod()
    return _round_trip(kind)


def check(kind: Format, *, probe: Probe = _probe) -> Check:
    try:
        replayed = probe(kind)
    except ValueError as error:
        return Check(kind.value, CheckStatus.FAILED, str(error))
    if not replayed:
        return Check(kind.value, CheckStatus.FAILED, DIFFERS)
    detail = "reads and writes" if kind in WRITABLE else "reads; never written"
    return Check(kind.value, CheckStatus.OK, detail)


def run() -> tuple[Check, ...]:
    return tuple(check(kind) for kind in Format)
