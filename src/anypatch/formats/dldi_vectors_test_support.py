from __future__ import annotations

import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from anypatch.formats.xdelta_vectors_test_support import noise

MAGIC = b"\xed\xa5\x8d\xbf Chishm\x00"
DRIVER_BASE = 0xBF800000
APP_BASE = 0x02012340
HEADER = 0x80
GLUE = (0x400, 0x440)
GOT = (0x440, 0x480)
BSS_SIZE = 0x100
FUNCTIONS = (0x80, 0x90, 0xA0, 0xB0, 0xC0, 0xD0)
POINTER_OFFSETS = (0x100, 0x203, 0x302, 0x404, 0x441, 0x47C)


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    app: bytes
    driver: bytes


@dataclass(frozen=True, slots=True)
class Driver:
    log2: int
    flags: int
    length: int
    seed: int


@dataclass(frozen=True, slots=True)
class App:
    size: int
    stubs: Sequence[int]
    allocated: int
    text_start: int
    seed: int


def placed(data: bytes, at: int, chunk: bytes) -> bytes:
    return data[:at] + chunk + data[at + len(chunk) :]


def words(*values: int) -> bytes:
    return b"".join(struct.pack("<I", value & 0xFFFFFFFF) for value in values)


def _sections(base: int, length: int) -> bytes:
    bss = (length, length + BSS_SIZE)
    edges = (0, length, *GLUE, *GOT, *bss)
    return words(*(base + edge for edge in edges))


def header(log2: int, flags: int, allocated: int, name: bytes) -> bytes:
    return MAGIC + bytes([1, log2, flags, allocated]) + name.ljust(48, b"\x00")


def driver(spec: Driver) -> bytes:
    head = header(spec.log2, spec.flags, spec.log2, b"anypatch test driver")
    io = b"TEST" + words(0x23, *(DRIVER_BASE + at for at in FUNCTIONS))
    body = head + _sections(DRIVER_BASE, spec.length) + io
    image = body + noise(spec.length - len(body), spec.seed)
    end = DRIVER_BASE + (1 << spec.log2)
    pointers = (DRIVER_BASE + 0x10, DRIVER_BASE - 4, end, end - 4, DRIVER_BASE, DRIVER_BASE + 7)
    for at, value in zip(POINTER_OFFSETS, pointers, strict=True):
        image = placed(image, at, words(value))
    return image


def _stub(spec: App) -> bytes:
    head = header(spec.allocated, 0, spec.allocated, b"Default (No interface)")
    startup = APP_BASE + HEADER
    calls = (startup, startup + 4, startup + 8, startup + 12, startup + 16, startup + 20)
    io = b"DLDI" + words(0, *calls)
    return head + words(spec.text_start, spec.text_start + 0x100, *([0] * 6)) + io


def app(spec: App) -> bytes:
    image = noise(spec.size, spec.seed)
    for at in spec.stubs:
        image = placed(image, at, _stub(spec))
    return image


def _case(name: str, target: App, patch: Driver) -> Case:
    return Case(name, app(target), driver(patch))


def cases() -> list[Case]:
    stock = App(0x10000, (0x2000,), 14, APP_BASE, 81)
    two = App(0x10000, (0x1000, 0x8000), 13, APP_BASE, 91)
    return [
        _case("plain", stock, Driver(11, 0, 0x800, 82)),
        _case("fix-all", stock, Driver(11, 1, 0x800, 83)),
        _case("glue-and-got", stock, Driver(11, 6, 0x800, 84)),
        _case("bss", stock, Driver(11, 8, 0x700, 85)),
        _case("every-flag", stock, Driver(12, 15, 0xC00, 86)),
        _case("short-file", stock, Driver(13, 15, 0x900, 87)),
        _case("full-space", stock, Driver(14, 15, 0x4000 - BSS_SIZE, 88)),
        _case("no-text-start", App(0x10000, (0x2000,), 14, 0, 89), Driver(11, 15, 0x700, 90)),
        _case("first-of-two", two, Driver(11, 1, 0x800, 92)),
    ]


RESULTS: Mapping[str, str] = {
    "plain": "791aa9980d73fb4ce68218926db96a4f11469fa1cf0dc23b0414bcbef22cc6cb",
    "fix-all": "b2b5a15f34b6506c4fa525afdf1882a7ee44639d11c4cd513e7a0220df88f087",
    "glue-and-got": "1aa734f1405dd05a05b1466cecf829a5b6c9ad97f5bdf2d95983ee45c218bd1b",
    "bss": "44785d5928ea53a98dc0fe07b172fb17c9e163be57a06fac60d85088ed6c9fcd",
    "every-flag": "0b3d92c58faf9b382cae627f1ccac223be8a7e986d870abca7f24aeb78356c5b",
    "short-file": "9761f1ebcbfa0107c1c290d0511fb6162d0c0539a3c9fad738f409aa2ff77fd9",
    "full-space": "c768c6df2de7af00aaa6fff6e67f88efa376e3b67c32e76d7c358f755003c92f",
    "no-text-start": "c700e789604b12ea029f01c4926d11b2e0733e66dd057de3194aea0e3023c7de",
    "first-of-two": "ff97009542682abbf5c613ee59e1055db897b73fa118302770e3e93e4e69c5ef",
}
