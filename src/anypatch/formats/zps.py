from __future__ import annotations

import struct

from n64_save_patches import ipswrite

HEADER_SIZE = 64
CRC_AT = 0x10


class ZpsError(ValueError):
    pass


def _pair(image: bytes) -> str:
    crc1, crc2 = struct.unpack_from(">II", image, CRC_AT)
    return f"{crc1:08X} {crc2:08X}"


def build(before: bytes, after: bytes) -> tuple[bytes, bytes]:
    if not ipswrite.fits(before, after):
        raise ZpsError("ZPS is IPS, so it cannot reach past 16 MiB; use IPS32, APS or xdelta")
    return ipswrite.build_variant(ipswrite.IPS, before, after), before[:HEADER_SIZE]


def check(before: bytes, header: bytes) -> None:
    if len(header) != HEADER_SIZE:
        raise ZpsError(f"a .HDR binding is {HEADER_SIZE} bytes, this one is {len(header)}")
    if len(before) < HEADER_SIZE or _pair(header) != _pair(before):
        have = _pair(before) if len(before) >= HEADER_SIZE else "no header"
        raise ZpsError(f"bound to {_pair(header)}, but this dump is {have}")


def apply(before: bytes, payload: bytes, header: bytes | None) -> bytes:
    if header is not None:
        check(before, header)
    return ipswrite.apply(before, payload)
