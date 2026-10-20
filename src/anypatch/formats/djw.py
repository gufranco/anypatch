from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

ALPHABET = 256
MAX_CODELEN = 20
TOTAL_CODES = MAX_CODELEN + 2
RUN_1 = 1
EXTRA_12OFFSET = 7
EXTRA_CODE_BITS = 4
CLCLEN_BITS = 4
MAX_CLCLEN = 15
GROUP_BITS = 3
SECTORSZ_BITS = 5
SECTORSZ_MULT = 5
GBCLEN_BITS = 3
MAX_GBCLEN = 7
CLEN_MTF = (0, 4, 5, 6, 7, 8, 9, 10, 3, 11, 2, 12, 13, 1, 14, 15, 16, 17, 18, 19, 20)
BYTE_DONE = 0x100


class DjwError(ValueError):
    pass


class Bits:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0
        self.byte = 0
        self.mask = BYTE_DONE

    def bit(self) -> int:
        if self.mask == BYTE_DONE:
            if self.pos == len(self.data):
                raise DjwError(
                    "the secondary section ends before its output is complete: end of input"
                )
            self.byte, self.mask = self.data[self.pos], 1
            self.pos += 1
        value = 1 if self.byte & self.mask else 0
        self.mask <<= 1
        return value

    def read(self, width: int) -> int:
        value = 0
        for _ in range(width):
            value = value << 1 | self.bit()
        return value


@dataclass(frozen=True, slots=True)
class Table:
    inorder: tuple[int, ...]
    base: tuple[int, ...]
    limit: tuple[int, ...]
    shortest: int
    longest: int

    @staticmethod
    def build(lengths: Sequence[int], longest_allowed: int) -> Table:
        counts = [sum(1 for n in lengths if n == size) for size in range(longest_allowed + 1)]
        used = [size for size in range(1, longest_allowed + 1) if counts[size]]
        if not used:
            return Table((), (), (), 1, 0)
        shortest, longest = used[0], used[-1]
        base, limit, first = [0] * (longest + 1), [0] * (longest + 1), [0] * (longest + 1)
        limit[shortest] = counts[shortest] - 1
        for size in range(shortest + 1, longest + 1):
            widened = (limit[size - 1] + 1) << 1
            first[size] = first[size - 1] + counts[size - 1]
            limit[size] = widened + counts[size] - 1
            base[size] = widened - first[size]
        inorder = tuple(s for size in used for s, n in enumerate(lengths) if n == size)
        return Table(inorder, tuple(base), tuple(limit), shortest, longest)

    def symbol(self, bits: Bits) -> int:
        code = 0
        for size in range(1, self.longest + 1):
            code = code << 1 | bits.bit()
            if size >= self.shortest and code <= self.limit[size]:
                return self.inorder[code - self.base[size]]
        raise DjwError("the secondary section holds an invalid code")


def _runs(bits: Bits, table: Table, initial: Sequence[int], count: int, skip: int) -> list[int]:
    order = list(initial)
    values: list[int] = []
    repeat = shift = pending = 0
    while len(values) < count:
        n = len(values)
        if skip and n >= skip and values[n - skip] == 0:
            values.append(0)
        elif repeat:
            values.append(order[0])
            repeat -= 1
        elif pending:
            order.insert(0, order.pop(pending))
            values.append(order[0])
            pending = 0
        else:
            code = table.symbol(bits)
            if code <= RUN_1:
                repeat, shift = (code + 1) << shift, shift + 1
            else:
                pending, shift = code - 1, 0
    if repeat:
        raise DjwError("the secondary section repeats past the end of its table")
    return values


def _group_lengths(bits: Bits, groups: int) -> list[list[int]]:
    count = bits.read(EXTRA_CODE_BITS) + EXTRA_12OFFSET
    lengths = [bits.read(CLCLEN_BITS) for _ in range(count)] + [0] * (TOTAL_CODES - count)
    table = Table.build(lengths, MAX_CLCLEN)
    flat = _runs(bits, table, CLEN_MTF, ALPHABET * groups, ALPHABET)
    return [flat[at : at + ALPHABET] for at in range(0, len(flat), ALPHABET)]


def _selectors(bits: Bits, groups: int, sectors: int) -> list[int]:
    if groups == 1:
        return [0] * sectors
    lengths = [bits.read(GBCLEN_BITS) for _ in range(groups + 1)]
    table = Table.build(lengths, MAX_GBCLEN)
    return _runs(bits, table, tuple(range(groups + 1)), sectors, 0)


def decode(data: bytes, size: int) -> bytes:
    if size <= 0:
        raise DjwError("a secondary section cannot decode to an empty output")
    bits = Bits(data)
    groups = bits.read(GROUP_BITS) + 1
    sector = (bits.read(SECTORSZ_BITS) + 1) * SECTORSZ_MULT if groups > 1 else size
    sectors = 1 + (size - 1) // sector
    tables = [Table.build(lengths, MAX_CODELEN) for lengths in _group_lengths(bits, groups)]
    chosen = _selectors(bits, groups, sectors)
    out = bytearray()
    for group in chosen:
        for _ in range(min(sector, size - len(out))):
            out.append(tables[group].symbol(bits))
    if bits.pos != len(data):
        raise DjwError(f"the secondary section has {len(data) - bits.pos} bytes after its output")
    return bytes(out)
