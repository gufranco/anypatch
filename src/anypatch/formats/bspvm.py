from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from anypatch.formats import imagesize

MASK = 0xFFFFFFFF
SIGN = 0x80000000
WRAP = 1 << 32
VARIABLES = 256
VARIABLE_MASK = 0xFF
NO_OPTIONS = 0xFFFFFFFF
SHA1_SIZE = 20
TEXT_END = b"\x00"
KIND_SIZES = {"w": 4, "h": 2, "r": 1}


class BspError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Limits:
    steps: int = 1 << 28
    stack: int = 1 << 24
    depth: int = 256


DEFAULT_LIMITS = Limits()


@dataclass(slots=True)
class Frame:
    patch: bytes
    ip: int = 0
    variables: list[int] = field(default_factory=lambda: [0] * VARIABLES)
    stack: list[int] = field(default_factory=list)
    buffer: str = ""
    waiting: int = 0


Handler = Callable[["Machine", tuple[int, ...]], "int | None"]
Table = Mapping[int, tuple[str, Handler]]


class Machine:
    def __init__(self, source: bytes, patch: bytes, choices: Sequence[int], limits: Limits) -> None:
        self.file = bytearray(source)
        self.source_size = len(source)
        self.pointer = 0
        self.locked = False
        self.frames = [Frame(patch)]
        self.messages: tuple[str, ...] = ()
        self.choices: Iterator[int] = iter(choices)
        self.limits = limits

    @property
    def frame(self) -> Frame:
        return self.frames[-1]

    def patch_bytes(self, address: int, size: int) -> bytes:
        patch = self.frame.patch
        if address + size > len(patch):
            raise BspError(
                f"read past the end of the {len(patch)}-byte patch space at {address:#x}"
            )
        return patch[address : address + size]

    def patch_value(
        self, address: int, size: int, order: Literal["little", "big"] = "little"
    ) -> int:
        return int.from_bytes(self.patch_bytes(address, size), order)

    def fetch(self, size: int) -> int:
        value = self.patch_value(self.frame.ip, size)
        self.frame.ip += size
        return value

    def operand(self, kind: str) -> int:
        if kind == "v":
            return self.value_of(self.fetch(1))
        return self.fetch(KIND_SIZES[kind])

    def value_of(self, index: int) -> int:
        return self.frame.variables[index & VARIABLE_MASK]

    def assign(self, index: int, value: int) -> None:
        self.frame.variables[index & VARIABLE_MASK] = value & MASK

    def text(self, address: int) -> str:
        end = self.frame.patch.find(TEXT_END, address)
        if end < 0:
            raise BspError(f"a string at {address:#x} runs past the end of the patch space")
        try:
            return self.frame.patch[address:end].decode("utf-8")
        except UnicodeDecodeError as error:
            raise BspError(f"the string at {address:#x} is not valid UTF-8") from error

    def push(self, value: int) -> None:
        self.resize_stack(len(self.frame.stack) + 1)
        self.frame.stack[-1] = value & MASK

    def pull(self) -> int:
        if not self.frame.stack:
            raise BspError("popped an empty stack")
        return self.frame.stack.pop()

    def poke(self, position: int, value: int) -> None:
        self.frame.stack[self.stack_index(position)] = value & MASK

    def peek(self, position: int) -> int:
        return self.frame.stack[self.stack_index(position)]

    def jump_to(self, address: int) -> None:
        self.frame.ip = address

    def place(self, position: int) -> None:
        if not 0 <= position <= MASK:
            raise BspError("the current file pointer overflows")
        self.pointer = position

    def lock(self, locked: bool) -> None:
        self.locked = locked

    def add_text(self, text: str) -> None:
        self.frame.buffer += text

    def flush_text(self) -> str:
        text = self.frame.buffer
        self.frame.buffer = ""
        return text

    def resize_stack(self, size: int) -> None:
        if size > self.limits.stack:
            raise BspError(f"the stack grows past {self.limits.stack} values")
        stack = self.frame.stack
        del stack[size:]
        stack.extend([0] * (size - len(stack)))

    def stack_index(self, position: int) -> int:
        depth = len(self.frame.stack)
        counted = position - WRAP + depth if position & SIGN else position
        if not 0 <= counted < depth:
            raise BspError(f"stack position {position:#x} is outside the {depth}-value stack")
        return depth - 1 - counted

    def move(self, position: int) -> None:
        if not self.locked:
            self.pointer = position & MASK

    def read_file(self, size: int, advance: bool) -> int:
        if self.pointer + size > len(self.file):
            raise BspError("read past the end of the file buffer")
        value = int.from_bytes(self.file[self.pointer : self.pointer + size], "little")
        if advance:
            self.move(self.pointer + size)
        return value

    def room(self, end: int) -> None:
        imagesize.check(end, source=self.source_size)

    def store(self, position: int, data: bytes) -> None:
        if not data:
            return
        self.room(position + len(data))
        if position > len(self.file):
            self.file.extend(bytes(position - len(self.file)))
        self.file[position : position + len(data)] = data

    def write(self, data: bytes) -> None:
        if self.pointer + len(data) > MASK:
            raise BspError("the current file pointer overflows")
        self.store(self.pointer, data)
        self.move(self.pointer + len(data))

    def truncate(self, size: int) -> None:
        self.room(size)
        del self.file[size:]
        self.file.extend(bytes(size - len(self.file)))

    def sha1(self) -> bytes:
        return hashlib.sha1(self.file, usedforsecurity=False).digest()

    def say(self, message: str) -> None:
        self.messages = (*self.messages, message)

    def choose(self, labels: Sequence[str]) -> int:
        if not labels:
            return NO_OPTIONS
        choice = next(self.choices, None)
        if choice is None:
            raise BspError(f"the patch asks to choose between: {', '.join(labels)}")
        if choice >= len(labels):
            raise BspError(f"choice {choice} is past the {len(labels)} options")
        return choice

    def nest(self, waiting: int, patch: bytes) -> None:
        if len(self.frames) >= self.limits.depth:
            raise BspError(f"nested patches past {self.limits.depth} levels")
        self.frame.waiting = waiting
        self.frames = [*self.frames, Frame(patch)]

    def step(self, table: Table) -> int | None:
        at = self.frame.ip
        opcode = self.fetch(1)
        entry = table.get(opcode)
        if entry is None:
            raise BspError(f"undefined opcode {opcode:#04x} at {at:#x}")
        kinds, handler = entry
        return handler(self, tuple(self.operand(kind) for kind in kinds))

    def finished(self, status: int) -> bool:
        self.frames = self.frames[:-1]
        if not self.frames:
            return True
        self.assign(self.frame.waiting, status)
        return False

    def outcome(self, status: int) -> bytes:
        if status == 0:
            return bytes(self.file)
        said = f": {self.messages[-1]}" if self.messages else ""
        raise BspError(f"the patch exited with status {status}{said}")

    def run(self, table: Table) -> bytes:
        for _ in range(self.limits.steps):
            status = self.step(table)
            if status is not None and self.finished(status):
                return self.outcome(status)
        raise BspError(f"the script ran past {self.limits.steps:,} instructions")
