from __future__ import annotations

from anypatch.formats.bspvm import MASK, BspError, Handler, Machine

IPS_HEADER = b"PATCH"
IPS_EOF = 0x454F46
IPS_OFFSET = 3
IPS_SIZE = 2


def _guarded(machine: Machine, length: int) -> None:
    if machine.pointer + length > MASK:
        raise BspError("the current file pointer overflows")


def writedata(machine: Machine, args: tuple[int, ...]) -> None:
    _guarded(machine, args[1])
    machine.write(machine.patch_bytes(args[0], args[1]))


def xordata(machine: Machine, args: tuple[int, ...]) -> None:
    _guarded(machine, args[1])
    data = machine.patch_bytes(args[0], args[1])
    present = machine.file[machine.pointer : machine.pointer + len(data)]
    mixed = bytes(left ^ right for left, right in zip(data, present, strict=False))
    machine.write(mixed + data[len(mixed) :])


def filler(size: int) -> Handler:
    def handler(machine: Machine, args: tuple[int, ...]) -> None:
        count, value = args
        if count == 0:
            return
        _guarded(machine, count * size)
        machine.room(machine.pointer + count * size)
        machine.write((value & ((1 << (8 * size)) - 1)).to_bytes(size, "little") * count)

    return handler


def _ips_record(machine: Machine, at: int) -> int:
    position = machine.patch_value(at, IPS_OFFSET, "big") + machine.pointer
    if position >= MASK:
        raise BspError("the current file pointer overflows")
    size = machine.patch_value(at + IPS_OFFSET, IPS_SIZE, "big")
    start = at + IPS_OFFSET + IPS_SIZE
    if size:
        machine.store(position, machine.patch_bytes(start, size))
        return start + size
    count = machine.patch_value(start, IPS_SIZE, "big")
    machine.store(position, machine.patch_bytes(start + IPS_SIZE, 1) * count)
    return start + IPS_SIZE + 1


def ipspatch(machine: Machine, args: tuple[int, ...]) -> None:
    if machine.patch_bytes(args[1], len(IPS_HEADER)) != IPS_HEADER:
        raise BspError("the embedded IPS patch has no PATCH header")
    at = args[1] + len(IPS_HEADER)
    while at + IPS_OFFSET <= len(machine.frame.patch):
        if machine.patch_value(at, IPS_OFFSET, "big") == IPS_EOF:
            machine.assign(args[0], at + IPS_OFFSET)
            return
        at = _ips_record(machine, at)
    raise BspError("the embedded IPS patch ends before its EOF")
