from __future__ import annotations

import re
import struct

MAGIC = b"\xed\xa5\x8d\xbf Chishm\x00"
VERSION = 1
HEADER = 0x80
ALIGNMENT = 4
VERSION_AT = 0x0C
SIZE_AT = 0x0D
FLAGS_AT = 0x0E
ALLOCATED_AT = 0x0F
TEXT_START = 0x40
STARTUP = 0x68
POINTERS = (0x40, 0x44, 0x48, 0x4C, 0x50, 0x54, 0x58, 0x5C, 0x68, 0x6C, 0x70, 0x74, 0x78, 0x7C)
FIX_ALL = 0x01
FIX_GLUE = 0x02
FIX_GOT = 0x04
FIX_BSS = 0x08
SECTIONS = (
    (FIX_ALL, "text and data", 0x40, 0x44),
    (FIX_GLUE, "glue", 0x48, 0x4C),
    (FIX_GOT, "global offset table", 0x50, 0x54),
)
BSS = (0x58, 0x5C)
WORD = struct.Struct("<I")
SIGNED = struct.Struct("<i")
MASK = 0xFFFFFFFF


class DldiError(ValueError):
    pass


def _signed(data: bytes | bytearray, at: int) -> int:
    value: int = SIGNED.unpack_from(data, at)[0]
    return value


def _section(app: bytes) -> int:
    found = (one.start() for one in re.finditer(re.escape(MAGIC), app))
    at = next((start for start in found if start % ALIGNMENT == 0), None)
    if at is None:
        raise DldiError("the app has no DLDI section")
    return at


def _checked(driver: bytes) -> None:
    if len(driver) < HEADER:
        raise DldiError(f"the driver is too short to hold the {HEADER}-byte DLDI header")
    if not driver.startswith(MAGIC):
        raise DldiError("not a DLDI driver: its header does not start with the DLDI magic")
    if driver[VERSION_AT] != VERSION:
        raise DldiError(f"DLDI version {driver[VERSION_AT]}; only {VERSION} is read")


def _space(app: bytes, at: int, driver: bytes) -> int:
    space = 1 << driver[SIZE_AT]
    reserved = 1 << app[at + ALLOCATED_AT]
    if driver[SIZE_AT] > app[at + ALLOCATED_AT]:
        raise DldiError(f"the driver needs {space} bytes, but the app reserves {reserved}")
    if len(driver) > space:
        raise DldiError(f"the driver file is {len(driver)} bytes, past the {space} it declares")
    if at + space > len(app):
        raise DldiError(f"the {space}-byte DLDI section at {at:#x} runs past the end of the app")
    return space


def _within(driver: bytes, name: str, fields: tuple[int, int], space: int) -> range:
    base = _signed(driver, TEXT_START)
    start, end = (_signed(driver, field) - base for field in fields)
    if start < 0 or end > space or end < start:
        raise DldiError(
            f"the {name} section, {start:#x} to {end:#x}, runs outside the driver space "
            f"of {space} bytes"
        )
    return range(start, end)


def _relocation(app: bytes, at: int, driver: bytes) -> int:
    placed = _signed(app, at + TEXT_START)
    if placed == 0:
        placed = _signed(app, at + STARTUP) - HEADER
    return placed - _signed(driver, TEXT_START)


def _area(app: bytes, at: int, driver: bytes, space: int) -> bytearray:
    area = bytearray(app[at : at + space + ALIGNMENT - 1])
    area[: len(driver)] = driver
    area[ALLOCATED_AT] = app[at + ALLOCATED_AT]
    return area


def _moved_header(area: bytearray, offset: int) -> None:
    for field in POINTERS:
        WORD.pack_into(area, field, (WORD.unpack_from(area, field)[0] + offset) & MASK)


def _moved_words(area: bytearray, span: range, bounds: range, offset: int) -> None:
    if span.stop + ALIGNMENT - 1 > len(area):
        raise DldiError("a section to relocate runs past the end of the app")
    for at in span:
        value = _signed(area, at)
        if value in bounds:
            WORD.pack_into(area, at, (value + offset) & MASK)


def apply(app: bytes, driver: bytes) -> bytes:
    _checked(driver)
    at = _section(app)
    space = _space(app, at, driver)
    flags = driver[FLAGS_AT]
    chosen = [one for one in SECTIONS if flags & one[0]]
    spans = [_within(driver, name, (first, last), space) for _, name, first, last in chosen]
    bss = _within(driver, "BSS", BSS, space) if flags & FIX_BSS else range(0)
    offset = _relocation(app, at, driver)
    low = _signed(driver, TEXT_START)
    area = _area(app, at, driver, space)
    _moved_header(area, offset)
    for span in spans:
        _moved_words(area, span, range(low, low + space), offset)
    area[bss.start : bss.stop] = bytes(len(bss))
    return app[:at] + bytes(area[:space]) + app[at + space :]
