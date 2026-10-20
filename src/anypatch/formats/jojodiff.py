from __future__ import annotations

from dataclasses import dataclass

from anypatch.formats import imagesize
from anypatch.formats.apswrite import differing_spans

ESC = 0xA7
MOD = 0xA6
INS = 0xA5
DEL = 0xA4
EQL = 0xA3
BKT = 0xA2
OPERATIONS = (MOD, INS, DEL, EQL, BKT)
ESCAPE = bytes([ESC])
ONE_BYTE = 252
PLUS = 253
WORD_CODE, DWORD_CODE, QWORD_CODE = 253, 254, 255
WIDE = {WORD_CODE: 2, DWORD_CODE: 4, QWORD_CODE: 8}
BYTE_LIMIT = ONE_BYTE
PLUS_LIMIT = PLUS + 0xFF
WORD_LIMIT = 0xFFFF
DWORD_LIMIT = 0xFFFFFFFF


class JojodiffError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _Data:
    chunk: bytes
    end: int
    following: int | None


def _escape_pair(patch: bytes, at: int) -> int:
    if at + 1 >= len(patch):
        raise JojodiffError("the patch ends after an escape byte")
    return patch[at + 1]


def _data(patch: bytes, at: int, operation: int) -> _Data:
    pieces: list[bytes] = []
    while at < len(patch):
        escape = patch.find(ESCAPE, at)
        stop = len(patch) if escape < 0 else escape
        pieces = [*pieces, patch[at:stop]]
        if escape < 0:
            return _Data(b"".join(pieces), stop, None)
        code = _escape_pair(patch, escape)
        if code in OPERATIONS and code != operation:
            return _Data(b"".join(pieces), escape + 2, code)
        pieces = [*pieces, ESCAPE if code == ESC else bytes([ESC, code])]
        at = escape + 2
    return _Data(b"".join(pieces), at, None)


def _length(patch: bytes, at: int) -> tuple[int, int]:
    if at >= len(patch):
        raise JojodiffError("the patch ends inside a length")
    first = patch[at]
    if first < ONE_BYTE:
        return first + 1, at + 1
    width = 1 if first == ONE_BYTE else WIDE[first]
    if at + 1 + width > len(patch):
        raise JojodiffError("the patch ends inside a length")
    value = int.from_bytes(patch[at + 1 : at + 1 + width], "big")
    return (value + PLUS if first == ONE_BYTE else value), at + 1 + width


def _operation(patch: bytes, at: int) -> tuple[int, int]:
    if patch[at] != ESC:
        return MOD, at
    code = _escape_pair(patch, at)
    return (code, at + 2) if code in OPERATIONS else (MOD, at)


@dataclass(frozen=True, slots=True)
class _State:
    position: int
    total: int
    pieces: tuple[bytes | slice, ...]


def _moved(source: bytes, state: _State, operation: int, length: int) -> _State:
    if operation == DEL:
        return _State(state.position + length, state.total, state.pieces)
    if operation == BKT:
        if length > state.position:
            raise JojodiffError(
                f"goes back {length} bytes from {state.position:#x}, before the start of the source"
            )
        return _State(state.position - length, state.total, state.pieces)
    if state.position + length > len(source):
        raise JojodiffError(
            f"copies {length} bytes from {state.position:#x}, past the {len(source):,}-byte source"
        )
    total = state.total + length
    imagesize.check(total, source=len(source))
    span = slice(state.position, state.position + length)
    return _State(state.position + length, total, (*state.pieces, span))


def _written(source: bytes, state: _State, operation: int, chunk: bytes) -> _State:
    total = state.total + len(chunk)
    imagesize.check(total, source=len(source))
    advance = len(chunk) if operation == MOD else 0
    return _State(state.position + advance, total, (*state.pieces, chunk))


def apply(source: bytes, patch: bytes) -> bytes:
    state = _State(0, 0, ())
    at = 0
    pending: int | None = None
    while at < len(patch) or pending is not None:
        operation, at = (pending, at) if pending is not None else _operation(patch, at)
        pending = None
        if operation in (MOD, INS):
            found = _data(patch, at, operation)
            state = _written(source, state, operation, found.chunk)
            at, pending = found.end, found.following
            continue
        length, at = _length(patch, at)
        state = _moved(source, state, operation, length)
    return b"".join(source[one] if isinstance(one, slice) else one for one in state.pieces)


def length_code(length: int) -> bytes:
    if length <= BYTE_LIMIT:
        return bytes([length - 1])
    if length <= PLUS_LIMIT:
        return bytes([ONE_BYTE, length - PLUS])
    if length <= WORD_LIMIT:
        return bytes([WORD_CODE]) + length.to_bytes(WIDE[WORD_CODE], "big")
    if length <= DWORD_LIMIT:
        return bytes([DWORD_CODE]) + length.to_bytes(WIDE[DWORD_CODE], "big")
    return bytes([QWORD_CODE]) + length.to_bytes(WIDE[QWORD_CODE], "big")


def _op(operation: int, body: bytes) -> bytes:
    return bytes([ESC, operation]) + body


def _escaped(chunk: bytes) -> bytes:
    return chunk.replace(ESCAPE, ESCAPE * 2)


def build(before: bytes, after: bytes) -> bytes:
    common = min(len(before), len(after))
    pieces: list[bytes] = []
    written = 0
    for start, chunk in differing_spans(before[:common], after[:common]):
        if start > written:
            pieces = [*pieces, _op(EQL, length_code(start - written))]
        pieces = [*pieces, _op(MOD, _escaped(chunk))]
        written = start + len(chunk)
    if common > written:
        pieces = [*pieces, _op(EQL, length_code(common - written))]
    if len(after) > common:
        pieces = [*pieces, _op(INS, _escaped(after[common:]))]
    return b"".join(pieces)
