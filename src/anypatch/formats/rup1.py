from __future__ import annotations

import hashlib
import re
import struct
import zlib
from dataclasses import dataclass

from anypatch.formats import imagesize, romtypes
from anypatch.formats.apswrite import differing_spans

MAGIC = b"NINJA1"
BINARY, BINARY_ZLIB, TEXT, TEXT_ZLIB = b"B ", b"BZ", b"T\n", b"TZ"
MODES = (BINARY, BINARY_ZLIB, TEXT, TEXT_ZLIB)
HEADER = len(MAGIC) + 2
DIGESTS = 1 + 4 + 16 + 20
END = b"EOF"
END_AS_OFFSET = int.from_bytes(END, "big")
LARGE = 0x1E00000
SAMPLE_HEAD = 0x1400000
SAMPLE_TAIL = 0xA00000
BODY_LIMIT = 3 * imagesize.LIMIT
UNKNOWN = "unk"
RECORD_LINE = re.compile(r"^([0-9A-Fa-f]+)(?: ([0-9A-Fa-f]*))?$")
SYSTEMS = {"snes": romtypes.SNES, "mega": romtypes.MD, "gb": romtypes.GB}
NAMES = (
    "raw",
    "nes",
    "snes",
    "n64",
    "gb",
    "gbc",
    "gba",
    "ngp",
    "ngpc",
    "sms",
    "gg",
    "mega",
    "pce",
    "ws",
    "wsc",
    "lynx",
    "jag",
    "gp32",
)


class Rup1Error(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Checks:
    system: str
    crc32: str
    md5: str
    sha1: str


def _number(value: int) -> bytes:
    raw = value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big")
    return bytes([len(raw)]) + raw


def _offset(value: int) -> bytes:
    if value == END_AS_OFFSET:
        return b"\x04" + value.to_bytes(4, "big")
    return _number(value)


def _digests(data: bytes) -> bytes:
    sample = _sample(data)
    crc = struct.pack(">I", zlib.crc32(sample))
    return crc + hashlib.md5(sample).digest() + hashlib.sha1(sample).digest()


def build(before: bytes, after: bytes) -> bytes:
    if len(after) < len(before):
        raise Rup1Error("NINJA 1 records only overwrite and extend, so it cannot shrink a file")
    spans = differing_spans(before, after[: len(before)])
    tail = [(len(before), after[len(before) :])] if len(after) > len(before) else []
    records = b"".join(_offset(at) + _number(len(data)) + data for at, data in [*spans, *tail])
    return MAGIC + BINARY + bytes([0]) + _digests(before) + records + bytes([len(END)]) + END


def _sample(dump: bytes) -> bytes:
    if len(dump) <= LARGE:
        return dump
    return dump[:SAMPLE_HEAD] + dump[-SAMPLE_TAIL:] + str(len(dump)).encode("ascii")


def _inflated(body: bytes) -> bytes:
    inflater = zlib.decompressobj()
    try:
        data = inflater.decompress(body, BODY_LIMIT)
    except zlib.error as error:
        raise Rup1Error(f"the compressed body does not decompress: {error}") from error
    if inflater.unconsumed_tail:
        raise Rup1Error(f"the compressed body decompresses past {BODY_LIMIT} bytes")
    return data


def _body(patch: bytes) -> tuple[bytes, bytes]:
    if not patch.startswith(MAGIC):
        raise Rup1Error("not a NINJA 1 patch: it does not start with NINJA1")
    mode = patch[len(MAGIC) : HEADER]
    if mode not in MODES:
        raise Rup1Error(f"NINJA 1 mode {mode!r}; only binary, text and their zlib forms are read")
    body = patch[HEADER:]
    return mode, _inflated(body) if mode in (BINARY_ZLIB, TEXT_ZLIB) else body


def _number_at(body: bytes, at: int) -> tuple[int, int]:
    if at >= len(body) or at + 1 + body[at] > len(body):
        raise Rup1Error(f"the patch ends inside a record at byte {at}")
    width = body[at]
    return int.from_bytes(body[at + 1 : at + 1 + width], "big"), at + 1 + width


def _binary_records(body: bytes) -> list[tuple[int, bytes]]:
    records: list[tuple[int, bytes]] = []
    at = DIGESTS
    while at < len(body):
        if body[at:] == bytes([len(END)]) + END:
            return records
        offset, at = _number_at(body, at)
        length, at = _number_at(body, at)
        if at + length > len(body):
            raise Rup1Error(f"the patch ends inside a record at byte {at}")
        records = [*records, (offset, body[at : at + length])]
        at += length
    raise Rup1Error("the patch has no EOF record")


def _binary(body: bytes) -> tuple[Checks, list[tuple[int, bytes]]]:
    if len(body) < DIGESTS:
        raise Rup1Error(f"the patch ends inside its {DIGESTS}-byte header")
    system = NAMES[body[0]] if body[0] < len(NAMES) else "raw"
    crc, md5, sha1 = body[1:5], body[5:21], body[21:DIGESTS]
    checks = Checks(system, *(_given(one) for one in (crc, md5, sha1)))
    return checks, _binary_records(body)


def _given(digest: bytes) -> str:
    return UNKNOWN if not any(digest) else digest.hex()


def _record(line: str) -> tuple[int, bytes]:
    found = RECORD_LINE.match(line)
    data = (found[2] or "") if found else ""
    if found is None or len(data) % 2:
        raise Rup1Error(f"the line {line!r} is not a hex offset and hex bytes")
    return int(found[1], 16), bytes.fromhex(data)


def _text(body: bytes) -> tuple[Checks, list[tuple[int, bytes]]]:
    lines = [line.strip() for line in body.decode("latin-1").split("\n")]
    meaningful = [line for line in lines if line and not line.startswith("#")]
    if not meaningful:
        raise Rup1Error("the patch has no header line")
    fields = (*meaningful[0].split(" "), UNKNOWN, UNKNOWN, UNKNOWN)[:4]
    checks = Checks(fields[0].lower(), *(one.lower() for one in fields[1:4]))
    return checks, [_record(line) for line in meaningful[1:]]


def _view(system: str, dump: bytes) -> bytes:
    kind = SYSTEMS.get(system)
    if kind is None or len(dump) > LARGE:
        return dump
    try:
        return romtypes.normalized(kind, dump).data
    except romtypes.RomTypeError:
        return dump


def _matches(checks: Checks, data: bytes) -> str:
    sample = _sample(data)
    found = (
        ("CRC32", checks.crc32, f"{zlib.crc32(sample):08x}"),
        ("MD5", checks.md5, hashlib.md5(sample).hexdigest()),
        ("SHA-1", checks.sha1, hashlib.sha1(sample).hexdigest()),
    )
    wrong = [
        f"{name} {want}, this dump {have}"
        for name, want, have in found
        if want not in (UNKNOWN, have)
    ]
    return "; ".join(wrong)


def _source(checks: Checks, dump: bytes) -> bytes:
    candidates = [_view(checks.system, dump), dump]
    for data in candidates:
        if not _matches(checks, data):
            return data
    raise Rup1Error(f"made for another dump: {_matches(checks, candidates[-1])}")


def apply(before: bytes, patch: bytes) -> bytes:
    mode, body = _body(patch)
    checks, records = _binary(body) if mode in (BINARY, BINARY_ZLIB) else _text(body)
    source = _source(checks, before)
    size = max([len(source), *(at + len(data) for at, data in records)])
    imagesize.check(size, source=len(before))
    out = bytearray(source.ljust(size, b"\x00"))
    for at, data in records:
        out[at : at + len(data)] = data
    return bytes(out)
