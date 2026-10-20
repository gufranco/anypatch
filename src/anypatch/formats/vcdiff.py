from __future__ import annotations

import lzma
import struct
import zlib
from dataclasses import dataclass

from n64_save_patches import djw, fgk
from n64_save_patches.apswrite import differing_spans

MAGIC = b"\xd6\xc3\xc4"
VERSION = 0
VCD_SECONDARY = 0x01
VCD_CODETABLE = 0x02
VCD_APPHEADER = 0x04
VCD_SOURCE = 0x01
VCD_TARGET = 0x02
VCD_ADLER32 = 0x04
DATA, INST, ADDR = 0x01, 0x02, 0x04
DJW_ID, LZMA_ID, FGK_ID = 1, 2, 16
NOOP, ADD, RUN, COPY = 0, 1, 2, 3
NEAR, SAME = 4, 3
SAME_SPAN = SAME * 256
VARINT_BYTES = 10
DEFAULT_WINDOW = 1 << 23
MIN_COPY = 4
MIN_RUN = 8
ADD_SHORT, COPY_SHORT = 17, 18
COPY_SELF_ESCAPE = 19

Half = tuple[int, int, int]
Instruction = tuple[Half, Half]
Step = tuple[int, int, bytes]


class VcdiffError(ValueError):
    pass


def _table() -> tuple[Instruction, ...]:
    none: Half = (NOOP, 0, 0)
    rows: list[Instruction] = [((RUN, 0, 0), none)]
    rows += [((ADD, size, 0), none) for size in range(18)]
    rows += [((COPY, size, mode), none) for mode in range(9) for size in (0, *range(4, 19))]
    rows += [
        ((ADD, add, 0), (COPY, copy, mode))
        for mode in range(6)
        for add in range(1, 5)
        for copy in range(4, 7)
    ]
    rows += [((ADD, add, 0), (COPY, 4, mode)) for mode in range(6, 9) for add in range(1, 5)]
    rows += [((COPY, 4, mode), (ADD, 1, 0)) for mode in range(9)]
    return tuple(rows)


TABLE = _table()


def varint(value: int) -> bytes:
    groups = [value & 0x7F]
    value >>= 7
    while value:
        groups.append(value & 0x7F | 0x80)
        value >>= 7
    return bytes(reversed(groups))


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def done(self) -> bool:
        return self.pos >= len(self.data)

    def byte(self) -> int:
        if self.done():
            raise VcdiffError(f"the patch ends at byte {self.pos} where more was expected")
        self.pos += 1
        return self.data[self.pos - 1]

    def take(self, size: int) -> bytes:
        if self.pos + size > len(self.data):
            raise VcdiffError(f"the patch ends at byte {self.pos} inside a {size}-byte field")
        self.pos += size
        return self.data[self.pos - size : self.pos]

    def varint(self) -> int:
        value = 0
        for _ in range(VARINT_BYTES):
            part = self.byte()
            value = value << 7 | part & 0x7F
            if not part & 0x80:
                return value
        raise VcdiffError(f"a number at byte {self.pos} is too long to be a size")


class _Cache:
    def __init__(self) -> None:
        self.near = [0] * NEAR
        self.next = 0
        self.same = [0] * SAME_SPAN

    def address(self, mode: int, here: int, addresses: _Reader) -> int:
        if mode == 0:
            found = addresses.varint()
        elif mode == 1:
            found = here - addresses.varint()
        elif mode < 2 + NEAR:
            found = self.near[mode - 2] + addresses.varint()
        else:
            found = self.same[(mode - 2 - NEAR) * 256 + addresses.byte()]
        self.near[self.next] = found
        self.next = (self.next + 1) % NEAR
        self.same[found % SAME_SPAN] = found
        return found


class _Secondary:
    def __init__(self, kind: int | None) -> None:
        self.kind = kind
        self.streams = {part: lzma.LZMADecompressor(lzma.FORMAT_XZ) for part in (DATA, INST, ADDR)}
        self.trees = {part: fgk.Decoder() for part in (DATA, INST, ADDR)}

    def expand(self, section: int, raw: bytes) -> bytes:
        if self.kind is None:
            raise VcdiffError(
                "a section is marked compressed, but the patch names no secondary compressor"
            )
        reader = _Reader(raw)
        size = reader.varint()
        payload = raw[reader.pos :]
        try:
            out = self._decoded(section, payload, size)
        except (djw.DjwError, fgk.FgkError, lzma.LZMAError) as error:
            raise VcdiffError(f"a compressed section does not decode: {error}") from error
        if len(out) != size:
            raise VcdiffError(f"a compressed section gave {len(out)} bytes, not {size}")
        return out

    def _decoded(self, section: int, payload: bytes, size: int) -> bytes:
        if self.kind == DJW_ID:
            return djw.decode(payload, size)
        if self.kind == FGK_ID:
            return self.trees[section].decode(payload, size)
        return self.streams[section].decompress(payload, max_length=size)


def _header(reader: _Reader) -> int | None:
    if reader.take(len(MAGIC)) != MAGIC:
        raise VcdiffError("not a VCDIFF patch: it does not start with the xdelta magic")
    if reader.byte() != VERSION:
        raise VcdiffError("an unknown VCDIFF version")
    flags = reader.byte()
    if flags & ~(VCD_SECONDARY | VCD_CODETABLE | VCD_APPHEADER):
        raise VcdiffError(f"unknown header flags {flags:#04x}")
    kind = reader.byte() if flags & VCD_SECONDARY else None
    if flags & VCD_CODETABLE:
        raise VcdiffError("a patch with its own code table, which xdelta3 never writes")
    if kind not in (None, DJW_ID, LZMA_ID, FGK_ID):
        raise VcdiffError(f"unknown secondary compressor {kind}")
    if flags & VCD_APPHEADER:
        reader.take(reader.varint())
    return kind


def _segment(indicator: int, reader: _Reader, source: bytes, out: bytes) -> bytes:
    if indicator & VCD_SOURCE and indicator & VCD_TARGET:
        raise VcdiffError("a window names both a source and a target segment")
    if not indicator & (VCD_SOURCE | VCD_TARGET):
        return b""
    length, position = reader.varint(), reader.varint()
    pool, name = (source, "this dump") if indicator & VCD_SOURCE else (out, "the output so far")
    if position + length > len(pool):
        raise VcdiffError(f"a window reads {length} bytes at {position:#x}, past the end of {name}")
    return pool[position : position + length]


@dataclass(frozen=True, slots=True)
class _Window:
    size: int
    data: bytes
    inst: bytes
    addr: bytes
    checksum: int | None


def _delta(indicator: int, reader: _Reader, secondary: _Secondary) -> _Window:
    length = reader.varint()
    start = reader.pos
    size, compressed = reader.varint(), reader.byte()
    lengths = (reader.varint(), reader.varint(), reader.varint())
    checksum = struct.unpack(">I", reader.take(4))[0] if indicator & VCD_ADLER32 else None
    sections = [reader.take(n) for n in lengths]
    if reader.pos - start != length:
        raise VcdiffError(
            f"a window's delta length says {length}, its contents take {reader.pos - start}"
        )
    data, inst, addr = (
        secondary.expand(bit, raw) if compressed & bit else raw
        for bit, raw in zip((DATA, INST, ADDR), sections, strict=True)
    )
    return _Window(size, data, inst, addr, checksum)


class _Decoder:
    def __init__(self, segment: bytes, window: _Window) -> None:
        self.segment = segment
        self.window = window
        self.target = bytearray()
        self.data = _Reader(window.data)
        self.addr = _Reader(window.addr)
        self.cache = _Cache()

    def copy(self, mode: int, size: int) -> None:
        here = len(self.segment) + len(self.target)
        address = self.cache.address(mode, here, self.addr)
        if address >= here:
            raise VcdiffError(f"a copy reads {address:#x}, which copies from ahead of {here:#x}")
        for at in range(address, address + size):
            inside = at < len(self.segment)
            self.target.append(self.segment[at] if inside else self.target[at - len(self.segment)])

    def execute(self, half: Half, size: int) -> None:
        kind, _, mode = half
        if kind == ADD:
            self.target.extend(self.data.take(size))
        elif kind == RUN:
            self.target.extend(bytes([self.data.byte()]) * size)
        else:
            self.copy(mode, size)
        if len(self.target) > self.window.size:
            raise VcdiffError(f"a window produced more than its declared size {self.window.size}")

    def run(self) -> bytes:
        inst = _Reader(self.window.inst)
        while not inst.done():
            for half in TABLE[inst.byte()]:
                if half[0] != NOOP:
                    self.execute(half, half[1] or inst.varint())
        if len(self.target) != self.window.size or not self.data.done() or not self.addr.done():
            raise VcdiffError("a window's sections do not match its declared size")
        return bytes(self.target)


def apply(source: bytes, patch: bytes) -> bytes:
    reader = _Reader(patch)
    secondary = _Secondary(_header(reader))
    out = bytearray()
    while not reader.done():
        indicator = reader.byte()
        if indicator & ~(VCD_SOURCE | VCD_TARGET | VCD_ADLER32):
            raise VcdiffError(f"unknown window flags {indicator:#04x}")
        segment = _segment(indicator, reader, source, bytes(out))
        window = _delta(indicator, reader, secondary)
        target = _Decoder(segment, window).run()
        if window.checksum is not None and zlib.adler32(target) != window.checksum:
            raise VcdiffError(
                f"the window at output {len(out):#x} does not match: wrong source dump"
            )
        out.extend(target)
    return bytes(out)


def _literal_end(chunk: bytes, at: int) -> int:
    for end in range(at + 1, len(chunk)):
        repeated = chunk[end : end + MIN_RUN]
        if len(repeated) == MIN_RUN and repeated.count(repeated[0]) == MIN_RUN:
            return end
    return len(chunk)


def _run_end(chunk: bytes, at: int) -> int:
    end = at + 1
    while end < len(chunk) and chunk[end] == chunk[at]:
        end += 1
    return end


def _literal(offset: int, chunk: bytes) -> list[Step]:
    steps: list[Step] = []
    at = 0
    while at < len(chunk):
        run = _run_end(chunk, at)
        kind, end = (RUN, run) if run - at >= MIN_RUN else (ADD, _literal_end(chunk, at))
        steps = [*steps, (kind, offset + at, chunk[at:end])]
        at = end
    return steps


def _changed(segment: bytes, target: bytes) -> list[tuple[int, bytes]]:
    common = min(len(segment), len(target))
    spans = differing_spans(segment[:common], target[:common])
    return [*spans, (common, target[common:])] if len(target) > common else spans


def _plan(segment: bytes, target: bytes) -> list[Step]:
    steps: list[Step] = []
    cursor = 0
    for offset, chunk in _changed(segment, target):
        if offset - cursor >= MIN_COPY:
            steps = [*steps, (COPY, cursor, target[cursor:offset])]
            start = offset
        else:
            start = cursor
        steps = [*steps, *_literal(start, target[start : offset + len(chunk)])]
        cursor = offset + len(chunk)
    if cursor < len(target):
        steps = [*steps, (COPY, cursor, target[cursor:])]
    return steps


def _code(kind: int, size: int) -> bytes:
    if kind == ADD:
        return bytes([1 + size]) if size <= ADD_SHORT else b"\x01" + varint(size)
    if kind == RUN:
        return b"\x00" + varint(size)
    if MIN_COPY <= size <= COPY_SHORT:
        return bytes([COPY_SELF_ESCAPE + 1 + size - MIN_COPY])
    return bytes([COPY_SELF_ESCAPE]) + varint(size)


def _sections(steps: list[Step]) -> tuple[bytes, bytes, bytes]:
    data = b"".join(piece[:1] if kind == RUN else piece for kind, _, piece in steps if kind != COPY)
    inst = b"".join(_code(kind, len(piece)) for kind, _, piece in steps)
    addr = b"".join(varint(offset) for kind, offset, _ in steps if kind == COPY)
    return data, inst, addr


def _window(source: bytes, target: bytes, start: int) -> bytes:
    segment = source[start : start + len(target)]
    data, inst, addr = _sections(_plan(segment, target))
    lengths = varint(len(data)) + varint(len(inst)) + varint(len(addr))
    body = varint(len(target)) + b"\x00" + lengths + struct.pack(">I", zlib.adler32(target))
    delta = body + data + inst + addr
    if segment:
        head = bytes([VCD_SOURCE | VCD_ADLER32]) + varint(len(segment)) + varint(start)
    else:
        head = bytes([VCD_ADLER32])
    return head + varint(len(delta)) + delta


def build(source: bytes, target: bytes, *, window: int = DEFAULT_WINDOW) -> bytes:
    windows = (
        _window(source, target[at : at + window], at) for at in range(0, len(target), window)
    )
    return MAGIC + bytes([VERSION, 0]) + b"".join(windows)
