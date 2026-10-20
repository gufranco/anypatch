from __future__ import annotations

import bz2
import lzma
import struct
import zlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from anypatch.formats import imagesize
from anypatch.formats.apswrite import differing_spans
from anypatch.formats.bdf import add

HDIFF13 = b"HDIFF13&"
SF20 = b"HDIFFSF20&"
PREFIX = b"HDIFF"
CODEC_LIMIT = 32
VARINT_LIMIT = 10
SIGN_BITS = 1
RLE_BITS = 2
RLE_ZERO, RLE_FULL, RLE_ONE, RLE_COPY = 0, 1, 2, 3
MIN_COVER = 8
HDIFF13_NUMBERS = 11
SF20_NUMBERS = 6
LZMA_PROPS = 5
LZMA1_LC, LZMA1_LP = 9, 5
LZMA2_PROP_LIMIT = 40


class HdiffError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Cover:
    old: int
    new: int
    length: int


def pack(value: int, *, tag: int = 0, bits: int = 0) -> bytes:
    limit = (1 << (7 - bits)) - 1
    groups = next(count for count in range(VARINT_LIMIT + 1) if value >> (7 * count) <= limit)
    first = value >> (7 * groups) | tag << (8 - bits) | (1 if groups else 0) << (7 - bits)
    rest = (
        value >> (7 * step) & 0x7F | (0x80 if step else 0) for step in range(groups - 1, -1, -1)
    )
    return bytes([first & 0xFF, *rest])


def unpack(data: bytes, at: int, bits: int) -> tuple[int, int, int]:
    if at >= len(data):
        raise HdiffError(f"the patch ends inside a number at byte {at}")
    code = data[at]
    tag = code >> (8 - bits) if bits else 0
    value, more, at = code & ((1 << (7 - bits)) - 1), code & 1 << (7 - bits), at + 1
    for _ in range(VARINT_LIMIT):
        if not more:
            return value, at, tag
        if at >= len(data):
            raise HdiffError(f"the patch ends inside a number at byte {at}")
        value, more, at = value << 7 | data[at] & 0x7F, data[at] & 0x80, at + 1
    raise HdiffError(f"a number at byte {at} is too long")


def _numbers(data: bytes, at: int, count: int) -> tuple[list[int], int]:
    values: list[int] = []
    for _ in range(count):
        value, at, _ = unpack(data, at, 0)
        values = [*values, value]
    return values, at


def _zlib(packed: bytes, size: int) -> bytes:
    try:
        bits = struct.unpack("b", packed[:1])[0]
        return zlib.decompressobj(bits).decompress(packed[1:], size + 1)
    except (zlib.error, ValueError, struct.error) as error:
        raise HdiffError(f"a zlib section does not decompress: {error}") from error


def _bz2(packed: bytes, size: int) -> bytes:
    out, rest, rounds = b"", packed, 0
    try:
        while rest and len(out) <= size and rounds < len(packed):
            decoder = bz2.BZ2Decompressor()
            out += decoder.decompress(rest, size + 1 - len(out))
            rest, rounds = (decoder.unused_data if decoder.eof else b""), rounds + 1
    except OSError as error:
        raise HdiffError(f"a bz2 section does not decompress: {error}") from error
    return out


def _raw(data: bytes, filters: list[dict[str, int]], size: int, name: str) -> bytes:
    try:
        decoder = lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=filters)
        return decoder.decompress(data, size + 1)
    except (lzma.LZMAError, ValueError) as error:
        raise HdiffError(f"a {name} section does not decompress: {error}") from error


def _lzma(packed: bytes, size: int) -> bytes:
    if not packed or packed[0] < LZMA_PROPS or len(packed) < 1 + packed[0]:
        raise HdiffError("a lzma section ends inside its properties")
    props = packed[1 : 1 + LZMA_PROPS]
    lc, lp, pb = props[0] % LZMA1_LC, props[0] // LZMA1_LC % LZMA1_LP, props[0] // 45
    dictionary = int.from_bytes(props[1:5], "little")
    filters = [{"id": lzma.FILTER_LZMA1, "lc": lc, "lp": lp, "pb": pb, "dict_size": dictionary}]
    return _raw(packed[1 + packed[0] :], filters, size, "lzma")


def _lzma2(packed: bytes, size: int) -> bytes:
    prop = packed[0] if packed else LZMA2_PROP_LIMIT + 1
    dictionary = (2 | prop & 1) << (prop // 2 + 11) if prop <= LZMA2_PROP_LIMIT else 0
    filters = [{"id": lzma.FILTER_LZMA2, "dict_size": dictionary}]
    return _raw(packed[1:], filters, size, "lzma2")


CODECS: dict[str, Callable[[bytes, int], bytes]] = {
    "zlib": _zlib,
    "pzlib": _zlib,
    "bz2": _bz2,
    "bzip2": _bz2,
    "pbz2": _bz2,
    "pbzip2": _bz2,
    "lzma": _lzma,
    "lzma2": _lzma2,
}


def _decoded(codec: str, packed: bytes, size: int) -> bytes:
    if not codec:
        raise HdiffError("a section is compressed but the patch names no codec")
    if codec.startswith("zstd"):
        raise HdiffError("zstd sections need a codec the Python standard library lacks")
    decoder = CODECS.get(codec)
    if decoder is None:
        raise HdiffError(f"unknown codec {codec!r}")
    data = decoder(packed, size)
    if len(data) != size:
        raise HdiffError(f"a {codec} section decodes to {len(data)} bytes, not {size}")
    return data


def _section(patch: bytes, at: int, sizes: tuple[int, int], codec: str) -> tuple[bytes, int]:
    size, packed_size = sizes
    stored = packed_size or size
    if at + stored > len(patch):
        raise HdiffError(f"the patch ends inside a section at byte {at}")
    raw = patch[at : at + stored]
    return (_decoded(codec, raw, size) if packed_size else raw), at + stored


def _covers13(buffer: bytes, count: int) -> Iterator[Cover]:
    old_back = new_back = at = 0
    for _ in range(count):
        delta, at, sign = unpack(buffer, at, SIGN_BITS)
        gap, at, _ = unpack(buffer, at, 0)
        length, at, _ = unpack(buffer, at, 0)
        cover = Cover(old_back - delta if sign else old_back + delta, new_back + gap, length)
        yield cover
        old_back, new_back = cover.old + length, cover.new + length


def _rle_piece(kind: int, length: int, code: bytes, at: int) -> tuple[bytes, int]:
    if kind == RLE_ZERO:
        return bytes(length), at
    if kind == RLE_FULL:
        return b"\xff" * length, at
    taken = 1 if kind == RLE_ONE else length
    if at + taken > len(code):
        raise HdiffError("the RLE codes end before the RLE stream does")
    piece = code[at : at + 1] * length if kind == RLE_ONE else code[at : at + length]
    return piece, at + taken


def _rle_pieces(ctrl: bytes, code: bytes, size: int) -> Iterator[bytes]:
    total = at = code_at = 0
    while total < size:
        if at >= len(ctrl):
            raise HdiffError("the RLE stream ends before the output does")
        length, at, kind = unpack(ctrl, at, RLE_BITS)
        if total + length + 1 > size:
            raise HdiffError("the RLE stream runs past the output")
        piece, code_at = _rle_piece(kind, length + 1, code, code_at)
        total += len(piece)
        yield piece
    if at != len(ctrl) or code_at != len(code):
        raise HdiffError("the RLE stream runs past the output")


def _checked_source(before: bytes, old: int, cover: Cover) -> bytes:
    if cover.old < 0 or cover.old + cover.length > len(before):
        raise HdiffError(
            f"a cover of {cover.length} bytes at {cover.old:#x} reaches past the "
            f"{len(before):,}-byte source"
        )
    return before[cover.old : cover.old + cover.length]


def _gap(diff: bytes, at: int, length: int) -> tuple[bytes, int]:
    if length < 0 or at + length > len(diff):
        raise HdiffError("the gaps need more diff bytes than the patch holds")
    return diff[at : at + length], at + length


def _assemble13(
    before: bytes, size: int, covers: Iterator[Cover], diff: bytes, adds: bytes
) -> bytes:
    pieces: list[bytes] = []
    new_back = diff_at = 0
    for cover in covers:
        if cover.new + cover.length > size:
            raise HdiffError(f"a cover at {cover.new:#x} writes past the {size:,}-byte result")
        gap, diff_at = _gap(diff, diff_at, cover.new - new_back)
        old = _checked_source(before, len(before), cover)
        pieces = [*pieces, gap, add(old, adds[cover.new : cover.new + cover.length])]
        new_back = cover.new + cover.length
    tail, diff_at = _gap(diff, diff_at, size - new_back)
    if diff_at != len(diff):
        raise HdiffError(f"{len(diff) - diff_at} diff bytes are left over")
    return b"".join([*pieces, tail])


def _checked(before: bytes, old: int, size: int) -> None:
    if old != len(before):
        raise HdiffError(f"made for a {old:,}-byte source, but this one is {len(before):,} bytes")
    imagesize.check(size, source=len(before))


def _hdiff13(before: bytes, patch: bytes, at: int, codec: str) -> bytes:
    numbers, at = _numbers(patch, at, HDIFF13_NUMBERS)
    size, old, count = numbers[:3]
    _checked(before, old, size)
    sections: list[bytes] = []
    for pair in zip(numbers[3::2], numbers[4::2], strict=True):
        section, at = _section(patch, at, pair, codec)
        sections = [*sections, section]
    if at != len(patch):
        raise HdiffError(f"{len(patch) - at} bytes follow the last section")
    covers, ctrl, code, diff = sections
    adds = b"".join(_rle_pieces(ctrl, code, size))
    return _assemble13(before, size, _covers13(covers, count), diff, adds)


class _Rle0:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.at = 0
        self.zeros = 0
        self.values = 0
        self.zero_next = True

    def _refill(self) -> None:
        length, self.at, _ = unpack(self.data, self.at, 0)
        if self.zero_next:
            self.zeros = length
        elif self.at + length > len(self.data):
            raise HdiffError("the rle0 data ends before its cover does")
        else:
            self.values = length
        self.zero_next = not self.zero_next

    def take(self, length: int) -> bytes:
        pieces: list[bytes] = []
        wanted, rounds = length, 0
        while wanted and rounds <= 2 * len(self.data) + 1:
            rounds += 1
            if not self.zeros and not self.values:
                self._refill()
            step = min(wanted, self.zeros or self.values)
            if self.zeros:
                piece, self.zeros = bytes(step), self.zeros - step
            else:
                piece, self.at, self.values = (
                    self.data[self.at : self.at + step],
                    self.at + step,
                    self.values - step,
                )
            pieces, wanted = [*pieces, piece], wanted - step
        return b"".join(pieces)


class _Stream:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.at = 0

    def take(self, length: int, what: str) -> bytes:
        if self.at + length > len(self.data):
            raise HdiffError(f"the patch ends inside a {what} at byte {self.at}")
        self.at += length
        return self.data[self.at - length : self.at]

    def number(self) -> int:
        value, self.at, _ = unpack(self.data, self.at, 0)
        return value


def _step_covers(buffer: bytes, previous: Cover) -> Iterator[Cover]:
    at = 0
    while at < len(buffer):
        delta, at, sign = unpack(buffer, at, SIGN_BITS)
        last_old, last_new = previous.old + previous.length, previous.new + previous.length
        gap, at, _ = unpack(buffer, at, 0)
        length, at, _ = unpack(buffer, at, 0)
        previous = Cover(last_old - delta if sign else last_old + delta, last_new + gap, length)
        yield previous


def _sf20_pieces(before: bytes, stream: _Stream, count: int) -> Iterator[bytes]:
    previous, remaining = Cover(0, 0, 0), count
    while remaining:
        cover_size, rle_size = stream.number(), stream.number()
        covers, rle = stream.take(cover_size, "step"), _Rle0(stream.take(rle_size, "step"))
        for cover in _step_covers(covers, previous):
            if not remaining or (cover.length == 0 and remaining > 1):
                raise HdiffError("a zero-length cover comes before the last")
            yield stream.take(cover.new - (previous.new + previous.length), "gap")
            yield add(_checked_source(before, len(before), cover), rle.take(cover.length))
            previous, remaining = cover, remaining - 1


def _sf20(before: bytes, patch: bytes, at: int, codec: str) -> bytes:
    numbers, at = _numbers(patch, at, SF20_NUMBERS)
    size, old, count, _, raw_size, packed_size = numbers
    _checked(before, old, size)
    body = patch[at:]
    stream = _Stream(_decoded(codec, body, raw_size) if packed_size else body)
    result = b"".join(_sf20_pieces(before, stream, count))
    if len(result) != size:
        raise HdiffError(f"the patch gives {len(result):,} bytes, not {size:,}")
    if stream.at != len(stream.data):
        raise HdiffError(f"{len(stream.data) - stream.at} bytes follow the last step")
    return result


def _header(patch: bytes) -> tuple[bytes, str, int]:
    if not patch.startswith(PREFIX):
        raise HdiffError("not an HDiffPatch patch: it does not start with HDIFF")
    kind = next((one for one in (HDIFF13, SF20) if patch.startswith(one)), None)
    if kind is None:
        raise HdiffError(
            "an HDiffPatch version that is not read; only HDIFF13 and HDIFFSF20 are read"
        )
    end = patch.find(b"\x00", len(kind), len(kind) + CODEC_LIMIT)
    if end < 0:
        raise HdiffError("the codec name has no end")
    return kind, patch[len(kind) : end].decode("latin-1"), end + 1


def apply(before: bytes, patch: bytes) -> bytes:
    kind, codec, at = _header(patch)
    reader = _hdiff13 if kind == HDIFF13 else _sf20
    return reader(before, patch, at, codec)


def _runs(before: bytes, after: bytes) -> list[tuple[int, int]]:
    common = min(len(before), len(after))
    starts = [
        0,
        *(start + len(chunk) for start, chunk in differing_spans(before[:common], after[:common])),
    ]
    ends = [*(start for start, _ in differing_spans(before[:common], after[:common])), common]
    return [
        (start, end - start)
        for start, end in zip(starts, ends, strict=True)
        if end - start >= MIN_COVER
    ]


def build(before: bytes, after: bytes) -> bytes:
    runs = _runs(before, after)
    covers = b"".join(
        pack(start - (previous[0] + previous[1]), bits=SIGN_BITS)
        + pack(start - (previous[0] + previous[1]))
        + pack(length)
        for previous, (start, length) in zip([(0, 0), *runs], runs, strict=False)
    )
    edges = [0, *(edge for start, length in runs for edge in (start, start + length)), len(after)]
    diff = b"".join(after[edges[at] : edges[at + 1]] for at in range(0, len(edges), 2))
    ctrl = pack(len(after) - 1, bits=RLE_BITS) if after else b""
    sizes = (len(after), len(before), len(runs), len(covers), 0, len(ctrl), 0, 0, 0, len(diff), 0)
    return HDIFF13 + b"\x00" + b"".join(pack(value) for value in sizes) + covers + ctrl + diff
