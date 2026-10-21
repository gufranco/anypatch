from __future__ import annotations

import hashlib
import struct
from collections.abc import Iterator, Sequence
from itertools import accumulate

from anypatch.formats.apswrite import differing_spans
from anypatch.formats.bspops import TABLE
from anypatch.formats.bspvm import DEFAULT_LIMITS, Limits, Machine

WRONG_SOURCE = b"This patch was made for a different source file."
WORD = struct.Struct("<I")
CHECKSHA1 = 0x16
JUMPNZ = 0x5A
TRUNCATE = 0x1E
SEEK = 0x60
WRITEDATA = 0x7C
EXIT = 0x06
PRINT = 0x68
RESULT = 0
CHECK_SIZE = 6 + 6 + 5
SPAN_SIZE = 5 + 9
EXIT_SIZE = 5
FAILURE_SIZE = 5 + 5
SHA1_SIZE = 20


def apply(
    source: bytes,
    patch: bytes,
    *,
    choices: Sequence[int] = (),
    limits: Limits = DEFAULT_LIMITS,
) -> bytes:
    return Machine(source, patch, choices, limits).run(TABLE)


def _spans(before: bytes, after: bytes) -> Iterator[tuple[int, bytes]]:
    common = min(len(before), len(after))
    yield from differing_spans(before[:common], after[:common])
    if len(after) > common:
        yield common, after[common:]


def _with(opcode: int, *operands: bytes) -> bytes:
    return bytes([opcode]) + b"".join(operands)


def build(before: bytes, after: bytes) -> bytes:
    spans = list(_spans(before, after))
    failure = CHECK_SIZE + SPAN_SIZE * len(spans) + EXIT_SIZE
    digest_at = failure + FAILURE_SIZE
    message_at = digest_at + SHA1_SIZE
    data_at = message_at + len(WRONG_SOURCE) + 1
    starts = list(accumulate((len(chunk) for _, chunk in spans), initial=data_at))
    check = (
        _with(CHECKSHA1, bytes([RESULT]), WORD.pack(digest_at))
        + _with(JUMPNZ, bytes([RESULT]), WORD.pack(failure))
        + _with(TRUNCATE, WORD.pack(len(after)))
    )
    writes = b"".join(
        _with(SEEK, WORD.pack(at)) + _with(WRITEDATA, WORD.pack(start), WORD.pack(len(chunk)))
        for (at, chunk), start in zip(spans, starts, strict=False)
    )
    ending = (
        _with(EXIT, WORD.pack(0)) + _with(PRINT, WORD.pack(message_at)) + _with(EXIT, WORD.pack(1))
    )
    data = hashlib.sha1(before, usedforsecurity=False).digest() + WRONG_SOURCE + b"\x00"
    return check + writes + ending + data + b"".join(chunk for _, chunk in spans)
