from __future__ import annotations

import struct
from collections.abc import Callable

from anypatch import api
from anypatch.doctor import Check, CheckStatus
from anypatch.formats import apsgba, dldi, pmsr
from anypatch.patchio import WRITABLE, Format

N64_MAGIC = b"\x80\x37\x12\x40"
BASE = N64_MAGIC + bytes((at * 7) & 0xFF for at in range(4, 0x400))
AFTER = BASE[:0x200] + b"\xde\xad\xbe\xef" + BASE[0x204:] + b"tail"
GBA_BLOCK = 0x10000
GBA_SOURCE = bytes(range(256)) * (GBA_BLOCK // 256)
GBA_TARGET = b"\x01" + GBA_SOURCE[1:]
STAR_ROD_RECORD = (0x10, b"star")
SAME_SIZE = (Format.PAT,)
DIFFERS = "a patch it wrote did not replay to its target"
DLDI_DRIVER_BASE = 0xBF800000
DLDI_APP_BASE = 0x02000000
DLDI_LOG2 = 7
DLDI_STUB_AT = 0x40

Probe = Callable[[Format], bool]


def _round_trip(kind: Format) -> bool:
    after = AFTER[: len(BASE)] if kind in SAME_SIZE else AFTER
    files = api.make(BASE, after, kind)
    name = f"selftest.{kind.value}"
    patch = api.load(files[f".{kind.value}"], name=name, binding=files.get(".hdr"))
    return api.apply(BASE, [patch]).image == after


def _gba() -> bool:
    return apsgba.apply(GBA_SOURCE, apsgba.build(GBA_SOURCE, GBA_TARGET)) == GBA_TARGET


def _star_rod() -> bool:
    offset, data = STAR_ROD_RECORD
    patch = pmsr.MAGIC + struct.pack(">III", 1, offset, len(data)) + data
    return pmsr.records(patch) == [STAR_ROD_RECORD]


def _dldi_header(base: int) -> bytes:
    fields = dldi.MAGIC + bytes([dldi.VERSION, DLDI_LOG2, 0, DLDI_LOG2])
    head = fields + bytes(dldi.TEXT_START - len(fields)) + struct.pack("<I", base)
    return head + bytes(dldi.HEADER - len(head))


def _dldi() -> bool:
    app = bytes(DLDI_STUB_AT) + _dldi_header(DLDI_APP_BASE) + bytes(1 << DLDI_LOG2)
    patched = dldi.apply(app, _dldi_header(DLDI_DRIVER_BASE))
    moved: int = struct.unpack_from("<I", patched, DLDI_STUB_AT + dldi.TEXT_START)[0]
    return moved == DLDI_APP_BASE


def _probe(kind: Format) -> bool:
    if kind is Format.DLDI:
        return _dldi()
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
