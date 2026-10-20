from __future__ import annotations

import functools
import random
import zlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from anypatch.formats import gdiff, ipswrite, pmsr, vcdiff
from anypatch.patchio import Format

KIB = 1 << 10
MIB = 1 << 20
CRC_BITS = 32
CRC_BYTES = 4
APS_RECORD = 0xFF
IPS_RECORD = 0xFFFF
GBA_BLOCK = 0x10000
SCATTERED = 500
SCATTER_LONGEST = 300
FILL_PAST_END = 0xA5
SHORT_VARINTS = (0x7F, 0x80, 0x3FFF, 0x4000)


@dataclass(frozen=True, slots=True)
class Boundary:
    name: str
    source: bytes
    target: bytes


Edit = tuple[int, int]


def seeded(seed: int, size: int) -> bytes:
    return random.Random(seed).randbytes(size)


def flipped(image: bytes, seed: int, edits: Sequence[Edit]) -> bytes:
    pick = random.Random(seed)
    out = bytearray(image)
    for at, length in edits:
        out[at : at + length] = bytes(
            byte ^ pick.randrange(1, 256) for byte in out[at : at + length]
        )
    return bytes(out)


def filled(image: bytes, at: int, length: int) -> bytes:
    value = image[at] ^ 0xFF if at < len(image) else FILL_PAST_END
    return image[:at] + bytes([value]) * length + image[at + length :]


def scattered(image: bytes, seed: int) -> list[Edit]:
    pick = random.Random(seed)
    return [
        (pick.randrange(len(image) - SCATTER_LONGEST), pick.randrange(1, SCATTER_LONGEST))
        for _ in range(SCATTERED)
    ]


def _unit_crcs(prefix_crc: int) -> list[int]:
    zero = zlib.crc32(bytes(CRC_BYTES), prefix_crc)
    tails = ((1 << bit).to_bytes(CRC_BYTES, "little") for bit in range(CRC_BITS))
    return [zlib.crc32(tail, prefix_crc) ^ zero for tail in tails]


def _basis(columns: Sequence[int]) -> dict[int, tuple[int, int]]:
    basis: dict[int, tuple[int, int]] = {}
    for bit, start in enumerate(columns):
        column, choice = start, 1 << bit
        for pivot in sorted(basis, reverse=True):
            if column >> pivot & 1:
                column, choice = column ^ basis[pivot][0], choice ^ basis[pivot][1]
        basis = {**basis, column.bit_length() - 1: (column, choice)}
    return basis


def _solved(columns: Sequence[int], wanted: int) -> int:
    basis = _basis(columns)
    answer = 0
    for pivot in sorted(basis, reverse=True):
        if wanted >> pivot & 1:
            wanted, answer = wanted ^ basis[pivot][0], answer ^ basis[pivot][1]
    return answer


def with_crc(image: bytes, crc: int) -> bytes:
    prefix = image[:-CRC_BYTES]
    prefix_crc = zlib.crc32(prefix)
    wanted = crc ^ zlib.crc32(bytes(CRC_BYTES), prefix_crc)
    tail = _solved(_unit_crcs(prefix_crc), wanted)
    return prefix + tail.to_bytes(CRC_BYTES, "little")


def _edited(name: str, seed: int, size: int, edits: Sequence[Edit]) -> Boundary:
    source = seeded(seed, size)
    return Boundary(name, source, flipped(source, seed + 1, edits))


def _resized(name: str, seed: int, before: int, after: int) -> Boundary:
    source = seeded(seed, before)
    grown = source + seeded(seed + 1, max(0, after - before))
    return Boundary(name, source, flipped(grown[:after], seed + 2, [(0x40, 0x10)]))


def _general() -> list[Boundary]:
    big = seeded(8, MIB)
    run = seeded(11, 512 * KIB)
    return [
        Boundary("identical", seeded(1, 4 * KIB), seeded(1, 4 * KIB)),
        Boundary("empty-to-data", b"", seeded(2, 300)),
        Boundary("data-to-empty", seeded(3, 300), b""),
        _edited("first-byte", 4, 64 * KIB, [(0, 1)]),
        _edited("last-byte", 5, 64 * KIB, [(64 * KIB - 1, 1)]),
        _resized("grow-by-one", 6, 64 * KIB, 64 * KIB + 1),
        _resized("shrink-by-one", 7, 64 * KIB, 64 * KIB - 1),
        Boundary("scattered", big, flipped(big, 9, scattered(big, 10))),
        Boundary("long-run", run, filled(run, 0x100, 0x20000)),
        _edited("long-literal", 12, 512 * KIB, [(0x100, 0x20000)]),
    ]


def _varints() -> list[Boundary]:
    return [
        _resized(f"varint-{size:#x}", 20 + at, size, size + 1)
        for at, size in enumerate(SHORT_VARINTS)
    ]


def _ips() -> list[Boundary]:
    limit = ipswrite.LIMIT
    end = ipswrite.END_AS_OFFSET
    eight = seeded(37, 8 * MIB)
    return [
        _edited("ips-eof-offset", 30, 8 * MIB, [(end, 1)]),
        Boundary("ips-run-at-eof-offset", eight, filled(eight, end, 16)),
        _edited("ips-last-offset", 31, limit, [(limit - 1, 1)]),
        _resized("ips-grow-to-limit", 32, limit - 1, limit),
        _edited("ips-past-limit-low-change", 33, limit + MIB, [(0x100, 4)]),
        _edited("ips-past-limit-high-change", 34, limit + MIB, [(limit, 4)]),
        _resized("ips-shrink-to-limit", 35, limit + MIB, limit),
        _resized("ips-shrink-below-limit", 36, limit + MIB, limit - 1),
    ]


def _records() -> list[Boundary]:
    return [
        _edited("aps-record-255", 40, 64 * KIB, [(0x100, APS_RECORD)]),
        _edited("aps-record-256", 41, 64 * KIB, [(0x100, APS_RECORD + 1)]),
        _edited("gba-block-edge", 42, 3 * GBA_BLOCK, [(GBA_BLOCK - 1, 2)]),
        _resized("gba-partial-block", 43, 100_000, 100_000),
        _edited("ips-record-65535", 44, 256 * KIB, [(0x100, IPS_RECORD)]),
        _edited("ips-record-65536", 45, 256 * KIB, [(0x100, IPS_RECORD + 1)]),
    ]


def _gdiff() -> list[Boundary]:
    lengths = (gdiff.INLINE_LIMIT, gdiff.INLINE_LIMIT + 1, gdiff.USHORT, gdiff.USHORT + 1)
    copies = (gdiff.UBYTE, gdiff.UBYTE + 1, gdiff.USHORT, gdiff.USHORT + 1)
    data = [
        _edited(f"gdiff-data-{n}", 50 + at, 512 * KIB, [(0x200, n)]) for at, n in enumerate(lengths)
    ]
    gaps = [
        _edited(f"gdiff-copy-{n}", 60 + at, 512 * KIB, [(0x10, 1), (0x11 + n, 1)])
        for at, n in enumerate(copies)
    ]
    far = _edited("gdiff-copy-past-ushort", 70, 512 * KIB, [(gdiff.USHORT - 2, 4)])
    return [*data, *gaps, far]


def _window(at: int, size: int) -> Boundary:
    near = min(vcdiff.DEFAULT_WINDOW - 2, size - 5)
    return _edited(f"xdelta-window-{size:#x}", 80 + at, size, [(near, 4), (size - 1, 1)])


def _windows() -> list[Boundary]:
    window = vcdiff.DEFAULT_WINDOW
    sizes = (window - 1, window, window + 1, 2 * window + 1)
    return [_window(at, size) for at, size in enumerate(sizes)]


def _star_rod() -> list[Boundary]:
    base = with_crc(seeded(90, pmsr.BASE_SIZE), pmsr.BASE_CRC)
    edited = flipped(base, 91, [(0x1000, 0x40), (pmsr.BASE_SIZE - 8, 4)])
    return [
        Boundary("pmsr-base-edit", base, edited),
        Boundary("pmsr-base-grow", base, edited + seeded(92, 0x1000)),
    ]


STAR_ROD = ("pmsr-base-edit", "pmsr-base-grow")
IPS_WALL = "whose offsets and sizes stop below 16 MiB"
SHRINK = "cannot shrink"
PAPER_MARIO = "made for Paper Mario USA 1.0"
REFUSED: Mapping[tuple[str, Format], str] = {
    ("identical", Format.APS_GBA): "the files are identical",
    ("empty-to-data", Format.ZPS): "binds through the source's first 64 bytes",
    ("data-to-empty", Format.EBP): SHRINK,
    ("data-to-empty", Format.PPF): SHRINK,
    ("shrink-by-one", Format.EBP): SHRINK,
    ("shrink-by-one", Format.PPF): SHRINK,
    ("ips-shrink-below-limit", Format.EBP): SHRINK,
    ("ips-shrink-below-limit", Format.PPF): SHRINK,
    ("ips-shrink-to-limit", Format.PPF): SHRINK,
    ("ips-shrink-to-limit", Format.EBP): IPS_WALL,
    ("ips-shrink-to-limit", Format.ZPS): IPS_WALL,
    ("ips-past-limit-high-change", Format.EBP): IPS_WALL,
    ("ips-past-limit-high-change", Format.ZPS): IPS_WALL,
    ("xdelta-window-0x1000001", Format.EBP): IPS_WALL,
    ("xdelta-window-0x1000001", Format.ZPS): IPS_WALL,
    ("pmsr-base-edit", Format.EBP): IPS_WALL,
    ("pmsr-base-edit", Format.ZPS): IPS_WALL,
    ("pmsr-base-grow", Format.EBP): IPS_WALL,
    ("pmsr-base-grow", Format.ZPS): IPS_WALL,
}


PAT_RESIZED = (
    "empty-to-data",
    "data-to-empty",
    "grow-by-one",
    "shrink-by-one",
    "varint-0x7f",
    "varint-0x80",
    "varint-0x3fff",
    "varint-0x4000",
    "ips-grow-to-limit",
    "ips-shrink-to-limit",
    "ips-shrink-below-limit",
    "pmsr-base-grow",
)
PAT_SIZE = "cannot change a file's size"


def refused(name: str, kind: Format) -> str:
    if kind is Format.PAT and name in PAT_RESIZED:
        return PAT_SIZE
    if kind is Format.PMSR and name not in STAR_ROD:
        return PAPER_MARIO
    return REFUSED.get((name, kind), "")


GROUPS: tuple[Callable[[], list[Boundary]], ...] = (
    _general,
    _varints,
    _ips,
    _records,
    _gdiff,
    _windows,
    _star_rod,
)


@functools.cache
def cases() -> tuple[Boundary, ...]:
    return tuple(case for group in GROUPS for case in group())


RECORDED: Mapping[str, tuple[int, int, str]] = {
    "identical": (4096, 4096, "91a99bdf56486ba1"),
    "empty-to-data": (0, 300, "e6795100b18fe455"),
    "data-to-empty": (300, 0, "1ad6af195f726cd0"),
    "first-byte": (65536, 65536, "8b1c213dcf548031"),
    "last-byte": (65536, 65536, "b0eac46558b7dfda"),
    "grow-by-one": (65536, 65537, "a6e7a5134e39e236"),
    "shrink-by-one": (65536, 65535, "a7337136504a3583"),
    "scattered": (1048576, 1048576, "d514a4ca6f157c82"),
    "long-run": (524288, 524288, "583cd6e1bf8b7b35"),
    "long-literal": (524288, 524288, "dc62a847caf6fd69"),
    "varint-0x7f": (127, 128, "8165f61ee7c8e55d"),
    "varint-0x80": (128, 129, "c6b199af4e4c4420"),
    "varint-0x3fff": (16383, 16384, "daecadd91cf5825b"),
    "varint-0x4000": (16384, 16385, "580fc1de32d8e3f2"),
    "ips-eof-offset": (8388608, 8388608, "8d5fdbab4f603d48"),
    "ips-run-at-eof-offset": (8388608, 8388608, "16a917511a3ea047"),
    "ips-last-offset": (16777216, 16777216, "5852d2e0356a65a9"),
    "ips-grow-to-limit": (16777215, 16777216, "f4b219c6c9fda470"),
    "ips-past-limit-low-change": (17825792, 17825792, "81c3facaa097e0da"),
    "ips-past-limit-high-change": (17825792, 17825792, "8a2aa87d72da54e2"),
    "ips-shrink-to-limit": (17825792, 16777216, "ba439606170bd3e4"),
    "ips-shrink-below-limit": (17825792, 16777215, "f7f7cbed246c6711"),
    "aps-record-255": (65536, 65536, "95c496871433770d"),
    "aps-record-256": (65536, 65536, "eea09900ecba9c53"),
    "gba-block-edge": (196608, 196608, "c66246f394b6ba95"),
    "gba-partial-block": (100000, 100000, "ed2cf1a0ed08de57"),
    "ips-record-65535": (262144, 262144, "008b69e0b3e3c7b9"),
    "ips-record-65536": (262144, 262144, "76774fa38affe9c8"),
    "gdiff-data-246": (524288, 524288, "7096c5eccbd3a1a7"),
    "gdiff-data-247": (524288, 524288, "15bf1c6994c603c6"),
    "gdiff-data-65535": (524288, 524288, "b5b36ed045c1c7cc"),
    "gdiff-data-65536": (524288, 524288, "2feccc13a9b6494f"),
    "gdiff-copy-255": (524288, 524288, "41daa324e8988788"),
    "gdiff-copy-256": (524288, 524288, "258c737dd1ebefa4"),
    "gdiff-copy-65535": (524288, 524288, "39f409d14b0c1ed0"),
    "gdiff-copy-65536": (524288, 524288, "683d982e60a47c20"),
    "gdiff-copy-past-ushort": (524288, 524288, "0c5529e5f7433e1b"),
    "xdelta-window-0x7fffff": (8388607, 8388607, "ae9e4af5017ae680"),
    "xdelta-window-0x800000": (8388608, 8388608, "5cd5668ac220a989"),
    "xdelta-window-0x800001": (8388609, 8388609, "73acc71f563c389c"),
    "xdelta-window-0x1000001": (16777217, 16777217, "5d7f27eba7fc24ee"),
    "pmsr-base-edit": (41943040, 41943040, "af6ec56175dca0c0"),
    "pmsr-base-grow": (41943040, 41947136, "5a208dc290fb1c43"),
}
