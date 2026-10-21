from __future__ import annotations

import operator
from collections.abc import Callable

from anypatch.formats.bspdata import filler, ipspatch, writedata, xordata
from anypatch.formats.bspvm import (
    MASK,
    NO_OPTIONS,
    SHA1_SIZE,
    SIGN,
    WRAP,
    BspError,
    Handler,
    Machine,
    Table,
)

WORD = 4
SURROGATES = range(0xD800, 0xE000)
UNICODE_END = 0x110000
SHIFT_COUNT = 0x1F
SHIFT_TYPE = 3
SHIFT_TYPE_AT = 5
SHIFT_VARIABLE = 0x80
TWO = ("w", "v")
PAIRED = ("rw", "rv")
FOUR = ("ww", "wv", "vw", "vv")
THREE = ("rww", "rwv", "rvw", "rvv")
COMPARED = ("vww", "vwv", "vvw", "vvv")
LONG = ("rrww", "rrwv", "rrvw", "rrvv")


def _nothing(machine: Machine, args: tuple[int, ...]) -> None:
    return None


def _return(machine: Machine, args: tuple[int, ...]) -> int | None:
    if not machine.frame.stack:
        return 0
    machine.jump_to(machine.pull())
    return None


def _jump(machine: Machine, args: tuple[int, ...]) -> None:
    machine.jump_to(args[0])


def _call(machine: Machine, args: tuple[int, ...]) -> None:
    machine.push(machine.frame.ip)
    machine.jump_to(args[0])


def _exit(machine: Machine, args: tuple[int, ...]) -> int:
    return args[0]


def _push(machine: Machine, args: tuple[int, ...]) -> None:
    machine.push(args[0])


def _pop(machine: Machine, args: tuple[int, ...]) -> None:
    machine.assign(args[0], machine.pull())


def _length(machine: Machine, args: tuple[int, ...]) -> None:
    machine.assign(args[0], len(machine.file))


def _pos(machine: Machine, args: tuple[int, ...]) -> None:
    machine.assign(args[0], machine.pointer)


def _reader(size: int, advance: bool) -> Handler:
    def handler(machine: Machine, args: tuple[int, ...]) -> None:
        machine.assign(args[0], machine.read_file(size, advance))

    return handler


def _getter(size: int) -> Handler:
    def handler(machine: Machine, args: tuple[int, ...]) -> None:
        machine.assign(args[0], machine.patch_value(args[1], size))

    return handler


def _stepper(size: int, step: int) -> Handler:
    def handler(machine: Machine, args: tuple[int, ...]) -> None:
        address = machine.value_of(args[1])
        machine.assign(args[1], address + step)
        machine.assign(args[0], machine.patch_value(address, size))

    return handler


def _checksha1(machine: Machine, args: tuple[int, ...]) -> None:
    digest = machine.sha1()
    expected = machine.patch_bytes(args[1], SHA1_SIZE)
    differing = (1 << at for at in range(SHA1_SIZE) if digest[at] != expected[at])
    machine.assign(args[0], sum(differing))


def _writer(size: int) -> Handler:
    def handler(machine: Machine, args: tuple[int, ...]) -> None:
        machine.write((args[0] & ((1 << (8 * size)) - 1)).to_bytes(size, "little"))

    return handler


def _truncate(machine: Machine, args: tuple[int, ...]) -> None:
    machine.truncate(args[0])


def _divided(first: int, second: int) -> int:
    if second == 0:
        raise BspError("division by zero")
    return first // second


def _remainder(first: int, second: int) -> int:
    if second == 0:
        raise BspError("division by zero")
    return first % second


def _calculation(function: Callable[[int, int], int]) -> Handler:
    def handler(machine: Machine, args: tuple[int, ...]) -> None:
        machine.assign(args[0], function(args[1], args[2]))

    return handler


def _comparison(test: Callable[[int, int], bool]) -> Handler:
    def handler(machine: Machine, args: tuple[int, ...]) -> None:
        if test(args[0], args[1]):
            machine.jump_to(args[2])

    return handler


def _when(zero: bool, then: Handler) -> Handler:
    def handler(machine: Machine, args: tuple[int, ...]) -> int | None:
        if (args[0] == 0) != zero:
            return None
        return then(machine, args[1:])

    return handler


def _seek(machine: Machine, args: tuple[int, ...]) -> None:
    machine.move(args[0])


def _relative(target: Callable[[Machine, int], int]) -> Handler:
    def handler(machine: Machine, args: tuple[int, ...]) -> None:
        if not machine.locked:
            machine.place(target(machine, args[0]))

    return handler


def _print(machine: Machine, args: tuple[int, ...]) -> None:
    machine.say(machine.text(args[0]))


def _options(machine: Machine, address: int) -> list[int]:
    starts = (
        machine.patch_value(at, WORD) for at in range(address, len(machine.frame.patch), WORD)
    )
    found: list[int] = []
    for start in starts:
        if start == NO_OPTIONS:
            return found
        found = [*found, start]
    raise BspError("a menu's option list runs past the end of the patch space")


def _menu(machine: Machine, args: tuple[int, ...]) -> None:
    labels = [machine.text(address) for address in _options(machine, args[1])]
    machine.assign(args[0], machine.choose(labels))


def _lock(locked: bool) -> Handler:
    def handler(machine: Machine, args: tuple[int, ...]) -> None:
        machine.lock(locked)

    return handler


def _truncatepos(machine: Machine, args: tuple[int, ...]) -> None:
    machine.truncate(machine.pointer)


def _jumptable(machine: Machine, args: tuple[int, ...]) -> None:
    machine.jump_to(machine.patch_value(machine.frame.ip + WORD * args[0], WORD))


def _set(machine: Machine, args: tuple[int, ...]) -> None:
    machine.assign(args[0], args[1])


def _stackwrite(machine: Machine, args: tuple[int, ...]) -> None:
    machine.poke(args[0], args[1])


def _stackread(machine: Machine, args: tuple[int, ...]) -> None:
    machine.assign(args[0], machine.peek(args[1]))


def _stackshift(machine: Machine, args: tuple[int, ...]) -> None:
    amount = args[0] - WRAP if args[0] & SIGN else args[0]
    size = len(machine.frame.stack) + amount
    if size < 0:
        raise BspError("popped an empty stack")
    machine.resize_stack(size)


def _setstacksize(machine: Machine, args: tuple[int, ...]) -> None:
    machine.resize_stack(args[0])


def _getstacksize(machine: Machine, args: tuple[int, ...]) -> None:
    machine.assign(args[0], min(len(machine.frame.stack), MASK))


def _pushpos(machine: Machine, args: tuple[int, ...]) -> None:
    machine.push(machine.pointer)


def _poppos(machine: Machine, args: tuple[int, ...]) -> None:
    machine.move(machine.pull())


def _bsppatch(machine: Machine, args: tuple[int, ...]) -> None:
    child = machine.patch_bytes(args[1], args[2])
    if not child:
        raise BspError("a nested patch of length 0")
    machine.nest(args[0], child)


def _counter(step: int) -> Handler:
    def handler(machine: Machine, args: tuple[int, ...]) -> None:
        machine.assign(args[0], machine.value_of(args[0]) + step)

    return handler


def _bufstring(machine: Machine, args: tuple[int, ...]) -> None:
    machine.add_text(machine.text(args[0]))


def _bufchar(machine: Machine, args: tuple[int, ...]) -> None:
    if args[0] >= UNICODE_END or args[0] in SURROGATES:
        raise BspError(f"{args[0]:#x} is not a Unicode character")
    machine.add_text(chr(args[0]) if args[0] else "")


def _bufnumber(machine: Machine, args: tuple[int, ...]) -> None:
    machine.add_text(str(args[0]))


def _printbuf(machine: Machine, args: tuple[int, ...]) -> None:
    machine.say(machine.flush_text())


def _clearbuf(machine: Machine, args: tuple[int, ...]) -> None:
    machine.flush_text()


def _shifted(kind: int, value: int, count: int) -> int:
    if kind == 0:
        return value << count
    if kind == 1:
        return value >> count
    if kind == 2:
        return (value << count) | (value >> (32 - count))
    signed = value - WRAP if value & SIGN else value
    return signed >> count


def _shift(machine: Machine, args: tuple[int, ...]) -> None:
    flags = machine.fetch(1)
    target = machine.fetch(1)
    value = machine.operand("v" if flags & SHIFT_VARIABLE else "w")
    count = flags & SHIFT_COUNT or machine.operand("v") & SHIFT_COUNT
    machine.assign(target, _shifted((flags >> SHIFT_TYPE_AT) & SHIFT_TYPE, value, count))


def _getvariable(machine: Machine, args: tuple[int, ...]) -> None:
    machine.assign(args[0], machine.value_of(args[1]))


def _addcarry(machine: Machine, args: tuple[int, ...]) -> None:
    result, carry, first, second = args
    carried = first + second > MASK
    machine.assign(carry, machine.value_of(carry) + carried)
    if result != carry:
        machine.assign(result, first + second)


def _subborrow(machine: Machine, args: tuple[int, ...]) -> None:
    result, borrow, first, second = args
    borrowed = first < second
    machine.assign(borrow, machine.value_of(borrow) - borrowed)
    if result != borrow:
        machine.assign(result, first - second)


def _longmul(machine: Machine, args: tuple[int, ...]) -> None:
    low, high, first, second = args
    product = first * second
    machine.assign(high, product >> 32)
    if low != high:
        machine.assign(low, product)


def _longmulacum(machine: Machine, args: tuple[int, ...]) -> None:
    low, high, first, second = args
    if low == high:
        machine.assign(low, first * second + machine.value_of(low))
        return
    total = ((machine.value_of(high) << 32) | machine.value_of(low)) + first * second
    machine.assign(low, total)
    machine.assign(high, total >> 32)


def _forms(base: int, forms: tuple[str, ...], handler: Handler) -> dict[int, tuple[str, Handler]]:
    return {base + index: (form, handler) for index, form in enumerate(forms)}


CALCULATIONS: dict[int, Callable[[int, int], int]] = {
    0x20: operator.add,
    0x24: operator.sub,
    0x28: operator.mul,
    0x2C: _divided,
    0x30: _remainder,
    0x34: operator.and_,
    0x38: operator.or_,
    0x3C: operator.xor,
}
COMPARISONS: dict[int, Callable[[int, int], bool]] = {
    0x40: operator.lt,
    0x44: operator.le,
    0x48: operator.gt,
    0x4C: operator.ge,
    0x50: operator.eq,
    0x54: operator.ne,
}
LONG_OPERATIONS: dict[int, Handler] = {
    0xB0: _addcarry,
    0xB4: _subborrow,
    0xB8: _longmul,
    0xBC: _longmulacum,
}
SINGLE: dict[int, tuple[str, Handler]] = {
    0x00: ("", _nothing),
    0x01: ("", _return),
    0x0A: ("r", _pop),
    0x0B: ("r", _length),
    0x0C: ("r", _reader(1, True)),
    0x0D: ("r", _reader(2, True)),
    0x0E: ("r", _reader(4, True)),
    0x0F: ("r", _pos),
    0x18: ("r", _writer(1)),
    0x19: ("v", _writer(1)),
    0x1A: ("h", _writer(2)),
    0x1B: ("v", _writer(2)),
    0x70: ("wr", filler(1)),
    0x71: ("wv", filler(1)),
    0x72: ("vr", filler(1)),
    0x73: ("vv", filler(1)),
    0x74: ("wh", filler(2)),
    0x75: ("wv", filler(2)),
    0x76: ("vh", filler(2)),
    0x77: ("vv", filler(2)),
    0x80: ("", _lock(True)),
    0x81: ("", _lock(False)),
    0x82: ("", _truncatepos),
    0x83: ("v", _jumptable),
    0x90: ("v", _when(True, _return)),
    0x91: ("v", _when(False, _return)),
    0x92: ("", _pushpos),
    0x93: ("", _poppos),
    0x98: ("rr", _stepper(1, 1)),
    0x99: ("rr", _stepper(2, 2)),
    0x9A: ("rr", _stepper(4, 4)),
    0x9B: ("r", _counter(1)),
    0x9C: ("rr", _stepper(1, -1)),
    0x9D: ("rr", _stepper(2, -2)),
    0x9E: ("rr", _stepper(4, -4)),
    0x9F: ("r", _counter(-1)),
    0xA6: ("", _printbuf),
    0xA7: ("", _clearbuf),
    0xAA: ("r", _getstacksize),
    0xAB: ("", _shift),
    0xAC: ("r", _reader(1, False)),
    0xAD: ("r", _reader(2, False)),
    0xAE: ("r", _reader(4, False)),
    0xAF: ("rv", _getvariable),
}
FAMILIES: tuple[tuple[int, tuple[str, ...], Handler], ...] = (
    (0x02, TWO, _jump),
    (0x04, TWO, _call),
    (0x06, TWO, _exit),
    (0x08, TWO, _push),
    (0x10, PAIRED, _getter(1)),
    (0x12, PAIRED, _getter(2)),
    (0x14, PAIRED, _getter(4)),
    (0x16, PAIRED, _checksha1),
    (0x1C, TWO, _writer(4)),
    (0x1E, TWO, _truncate),
    (0x58, ("vw", "vv"), _when(True, _jump)),
    (0x5A, ("vw", "vv"), _when(False, _jump)),
    (0x5C, ("vw", "vv"), _when(True, _call)),
    (0x5E, ("vw", "vv"), _when(False, _call)),
    (0x60, TWO, _seek),
    (0x62, TWO, _relative(lambda machine, value: machine.pointer + value)),
    (0x64, TWO, _relative(lambda machine, value: machine.pointer - value)),
    (0x66, TWO, _relative(lambda machine, value: len(machine.file) - value)),
    (0x68, TWO, _print),
    (0x6A, PAIRED, _menu),
    (0x6C, FOUR, xordata),
    (0x78, FOUR, filler(4)),
    (0x7C, FOUR, writedata),
    (0x84, PAIRED, _set),
    (0x86, PAIRED, ipspatch),
    (0x88, FOUR, _stackwrite),
    (0x8C, PAIRED, _stackread),
    (0x8E, TWO, _stackshift),
    (0x94, THREE, _bsppatch),
    (0xA0, TWO, _bufstring),
    (0xA2, TWO, _bufchar),
    (0xA4, TWO, _bufnumber),
    (0xA8, TWO, _setstacksize),
    *((base, THREE, _calculation(function)) for base, function in CALCULATIONS.items()),
    *((base, COMPARED, _comparison(test)) for base, test in COMPARISONS.items()),
    *((base, LONG, handler) for base, handler in LONG_OPERATIONS.items()),
)
TABLE: Table = {
    **SINGLE,
    **{
        opcode: entry
        for base, forms, handler in FAMILIES
        for opcode, entry in _forms(base, forms, handler).items()
    },
}
