from __future__ import annotations

import bz2

from anypatch.formats import bdf, imagesize

MAGIC = b"ENDSLEY/BSDIFF43"
HEADER = len(MAGIC) + bdf.FIELD
STALLS = 16
LEFTOVER_PROBE = 1 << 20


class Bsdiff43Error(ValueError):
    pass


def build(before: bytes, after: bytes) -> bytes:
    common = min(len(before), len(after))
    triple = bdf.offt(common) + bdf.offt(len(after) - common) + bdf.offt(0) if after else b""
    stream = triple + bdf.subtract(after[:common], before[:common]) + after[common:]
    return MAGIC + bdf.offt(len(after)) + bz2.compress(stream)


class _Stream:
    def __init__(self, compressed: bytes) -> None:
        self.decoder = bz2.BZ2Decompressor()
        self.pending = compressed
        self.buffer = b""

    def _more(self, wanted: int) -> bytes:
        try:
            chunk = self.decoder.decompress(self.pending, max_length=wanted)
        except OSError as error:
            raise Bsdiff43Error(f"the bzip2 stream does not decompress: {error}") from error
        self.pending = b""
        return chunk

    def take(self, count: int, what: str) -> bytes:
        stalls = 0
        while len(self.buffer) < count:
            chunk = b"" if self.decoder.eof else self._more(count - len(self.buffer))
            stalls = 0 if chunk else stalls + 1
            if stalls > STALLS or (not chunk and self.decoder.needs_input):
                raise Bsdiff43Error(f"the stream ends inside {what}")
            self.buffer += chunk
        taken, self.buffer = self.buffer[:count], self.buffer[count:]
        return taken

    def leftover(self) -> tuple[int, int]:
        drained = b"" if self.decoder.eof else self._more(LEFTOVER_PROBE)
        unused = len(self.decoder.unused_data) if self.decoder.eof else 0
        return len(self.buffer) + len(drained), unused


def _triple(stream: _Stream, written: int, size: int) -> tuple[bytes, bytes, bytes]:
    control = stream.take(bdf.TRIPLE, "a control triple")
    adding, extra = bdf.read_offt(control, 0), bdf.read_offt(control, bdf.FIELD)
    if adding < 0 or extra < 0:
        raise Bsdiff43Error("a control triple holds a negative length")
    if written + adding + extra > size:
        raise Bsdiff43Error(f"a control triple writes past the {size:,}-byte target")
    return control, stream.take(adding, "the diff bytes"), stream.take(extra, "the extra bytes")


def _blocks(stream: _Stream, size: int) -> bdf.Blocks:
    parts: list[tuple[bytes, bytes, bytes]] = []
    written = 0
    for _ in range(size + 1):
        if written == size:
            break
        control, diff, extra = _triple(stream, written, size)
        parts = [*parts, (control, diff, extra)]
        written += len(diff) + len(extra)
    if written < size:
        raise Bsdiff43Error(f"more control triples than a {size:,}-byte target allows")
    control, diff, extra = (b"".join(part[k] for part in parts) for k in range(3))
    return bdf.Blocks(control, diff, extra, size)


def _checked_end(stream: _Stream) -> None:
    decoded, unused = stream.leftover()
    if decoded:
        raise Bsdiff43Error(f"{decoded} bytes follow the last control triple")
    if unused:
        raise Bsdiff43Error(f"{unused} bytes follow the stream")


def apply(before: bytes, patch: bytes) -> bytes:
    if not patch.startswith(MAGIC):
        raise Bsdiff43Error("not a BSDIFF43 patch: it does not start with ENDSLEY/BSDIFF43")
    if len(patch) < HEADER:
        raise Bsdiff43Error(f"the patch is {len(patch)} bytes, too short to hold its header")
    size = bdf.read_offt(patch, len(MAGIC))
    if size < 0:
        raise Bsdiff43Error("the header holds a negative size")
    imagesize.check(size, source=len(before))
    stream = _Stream(patch[HEADER:])
    blocks = _blocks(stream, size)
    _checked_end(stream)
    return bdf.replay(before, blocks)
