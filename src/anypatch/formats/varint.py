from __future__ import annotations

LOW = 0x7F
STOP = 0x80
SHIFT = 7
LONGEST = 10


class VarintError(ValueError):
    pass


def encode(value: int) -> bytes:
    out = bytearray()
    for _ in range(LONGEST):
        low, value = value & LOW, value >> SHIFT
        if value == 0:
            out.append(STOP | low)
            return bytes(out)
        out.append(low)
        value -= 1
    raise VarintError(f"{value} is too large for a byuu number")


def decode(data: bytes, at: int) -> tuple[int, int]:
    value, shift = 0, 1
    for pos in range(at, at + LONGEST):
        if pos >= len(data):
            raise VarintError(f"the patch ends inside a number at byte {at}")
        byte = data[pos]
        value += (byte & LOW) * shift
        if byte & STOP:
            return value, pos + 1
        shift <<= SHIFT
        value += shift
    raise VarintError(f"the number at byte {at} is too long")
