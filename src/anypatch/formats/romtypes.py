from __future__ import annotations

import struct
from collections.abc import Callable, Sequence
from dataclasses import dataclass

RAW, NES, SNES, N64, GB, SMS, MD, PCE, LYNX = 0, 1, 3, 4, 5, 6, 7, 8, 9
KIB = 1024
BANK = 32 * KIB
SMD_BLOCK = 16 * KIB
COPIER_HEADER = 0x200
INES_HEADER = 0x10
LYNX_HEADER = 0x40
UNIF_START = 0x20
UNIF_ID = 4
UNIF_SIZE = 4
FFE_MARK_AT = 8
FFE_MARK = b"\xaa\xbb"
NSRT_AT = 0x1E8
UFO_AT = 8
GB_BANK = 0x4000
GB_LOGO_AT = 0x104
GB_LOGO = b"\xce\xed\x66\x66"
PCE_BANK = 0x1000
SMS_SEGA_AT = 0x7FF4
MD_SEGA_AT = 0x100
V64 = b"\x37\x80\x40\x12"
LOROM_INFO = 0x7FD5
HIROM_INFO = 0xFFD5
CHECKSUM_PAIR = 7
CHECKSUM_TOTAL = 0xFFFF

CHART_20MBIT = (
    *range(1, 80, 2),
    *range(64, 80, 2),
    *range(32, 64, 2),
    *range(0, 32, 2),
)
CHART_24MBIT = (
    *range(1, 96, 2),
    *range(64, 96, 2),
    *range(0, 64, 2),
)
CHART_48MBIT = (
    *range(129, 192, 2),
    *range(128, 192, 2),
    *range(1, 128, 2),
    *range(0, 128, 2),
)
CHARTS = {0x50: CHART_20MBIT, 0x60: CHART_24MBIT, 0xC0: CHART_48MBIT}

Restore = Callable[[bytes], bytes]


class RomTypeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Normalized:
    data: bytes
    restore: Restore


def _unchanged(result: bytes) -> bytes:
    return result


def _prefixed(header: bytes) -> Restore:
    return lambda result: header + result


def _unif_chunks(image: bytes) -> list[tuple[bytes, int, int]]:
    chunks: list[tuple[bytes, int, int]] = []
    at = UNIF_START
    while at + UNIF_ID + UNIF_SIZE <= len(image):
        name = image[at : at + UNIF_ID]
        size = struct.unpack_from("<I", image, at + UNIF_ID)[0]
        start = at + UNIF_ID + UNIF_SIZE
        if start + size > len(image):
            raise RomTypeError(
                f"the UNIF chunk {name.decode('latin-1')} at {at:#x} runs past the end"
            )
        chunks = [*chunks, (name, start, size)]
        at = start + size
    return [one for one in chunks if one[0][:3] in (b"PRG", b"CHR")]


def _unif(image: bytes) -> Normalized:
    banks = _unif_chunks(image)
    data = b"".join(image[start : start + size] for _, start, size in banks)

    def restore(result: bytes) -> bytes:
        out = bytearray(image)
        used = 0
        for _, start, size in banks:
            piece = result[used : used + size]
            out[start : start + len(piece)] = piece
            used += size
        return bytes(out)

    return Normalized(data, restore)


def _nes(image: bytes) -> Normalized:
    if image.startswith(b"NES"):
        return Normalized(image[INES_HEADER:], _prefixed(image[:INES_HEADER]))
    if image[FFE_MARK_AT : FFE_MARK_AT + 2] == FFE_MARK:
        return Normalized(image[COPIER_HEADER:], _prefixed(image[:COPIER_HEADER]))
    if image.startswith(b"UNIF"):
        return _unif(image)
    raise RomTypeError("a NES patch needs an iNES, Famtasia or UNIF dump")


def _banks(image: bytes) -> list[bytes]:
    return [image[at : at + BANK] for at in range(0, len(image), BANK)]


def _halves(image: bytes) -> bytes:
    banks = _banks(image)
    half = len(banks) // 2
    return b"".join(banks[half + at] + banks[at] for at in range(half))


def _charted(image: bytes, chart: Sequence[int]) -> bytes:
    banks = _banks(image)
    return b"".join(banks[chart.index(at)] for at in range(len(chart)))


def _info(image: bytes, at: int) -> tuple[bool, bool]:
    if at + CHECKSUM_PAIR + 4 > len(image):
        return False, False
    inverse, checksum = struct.unpack_from("<HH", image, at + CHECKSUM_PAIR)
    return inverse + checksum == CHECKSUM_TOTAL, bool(image[at] % 0x10 % 2)


def _snes_order(image: bytes, ufo: bool) -> bytes:
    summed, odd = _info(image, LOROM_INFO)
    if summed and not odd:
        return image
    if summed:
        chart = CHARTS.get(len(image) // BANK) if len(image) % BANK == 0 and not ufo else None
        return _charted(image, chart) if chart else _halves(image)
    if _info(image, HIROM_INFO)[1]:
        return image
    raise RomTypeError("this dump has no LoROM or HiROM header, so it is not a SNES ROM")


def _snes(image: bytes) -> Normalized:
    nsrt = image[NSRT_AT : NSRT_AT + 4] == b"NSRT"
    ufo = image[UFO_AT : UFO_AT + 8] == b"SUPERUFO"
    headered = len(image) % BANK != 0
    plain = image[COPIER_HEADER:] if headered else image
    restore = _prefixed(image[:COPIER_HEADER]) if nsrt else _unchanged
    return Normalized(_snes_order(plain, ufo), restore)


def _swapped(image: bytes) -> bytes:
    out = bytearray(image)
    out[0::2], out[1::2] = image[1::2], image[0::2]
    return bytes(out)


def _n64(image: bytes) -> Normalized:
    data = _swapped(image) if image.startswith(V64) and len(image) % 2 == 0 else image
    return Normalized(data, _unchanged)


def _gb(image: bytes) -> Normalized:
    data = image[COPIER_HEADER:] if len(image) % GB_BANK else image
    if data[GB_LOGO_AT : GB_LOGO_AT + len(GB_LOGO)] != GB_LOGO:
        raise RomTypeError("this dump has no Nintendo logo at 0x104, so it is not a Game Boy ROM")
    return Normalized(data, _unchanged)


def _smd_block(chunk: bytes) -> bytes:
    half = len(chunk) // 2
    out = bytearray(len(chunk))
    out[0::2], out[1::2] = chunk[:half], chunk[half:]
    return bytes(out)


def _sega(sega_at: int) -> Callable[[bytes], Normalized]:
    def read(image: bytes) -> Normalized:
        if image[sega_at : sega_at + 4] == b"SEGA":
            return Normalized(image, _unchanged)
        if image[FFE_MARK_AT : FFE_MARK_AT + 2] == FFE_MARK:
            body = image[COPIER_HEADER:]
            blocks = (body[at : at + SMD_BLOCK] for at in range(0, len(body), SMD_BLOCK))
            return Normalized(b"".join(_smd_block(one) for one in blocks), _unchanged)
        raise RomTypeError("this dump is neither a plain image with SEGA nor an SMD dump")

    return read


def _pce(image: bytes) -> Normalized:
    data = image[COPIER_HEADER:] if len(image) % PCE_BANK else image
    return Normalized(data, _unchanged)


def _lynx(image: bytes) -> Normalized:
    if image.startswith(b"LYNX"):
        return Normalized(image[LYNX_HEADER:], _prefixed(image[:LYNX_HEADER]))
    return Normalized(image, _unchanged)


READERS: dict[int, Callable[[bytes], Normalized]] = {
    NES: _nes,
    SNES: _snes,
    N64: _n64,
    GB: _gb,
    SMS: _sega(SMS_SEGA_AT),
    MD: _sega(MD_SEGA_AT),
    PCE: _pce,
    LYNX: _lynx,
}


def normalized(kind: int, image: bytes) -> Normalized:
    reader = READERS.get(kind)
    return reader(image) if reader else Normalized(image, _unchanged)
