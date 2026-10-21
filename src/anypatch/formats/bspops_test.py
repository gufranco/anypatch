import struct

import pytest

from anypatch.formats import bsp, bspvm


def word(value: int) -> bytes:
    return struct.pack("<I", value & 0xFFFFFFFF)


EXIT_0 = b"\x06" + word(0)


class TestTheFilePointer:
    def test_a_locked_pointer_ignores_every_move(self):
        # Arrange
        moves = b"\x60" + word(9) + b"\x62" + word(1) + b"\x64" + word(1) + b"\x66" + word(1)
        program = b"\x80" + moves + b"\x93" + b"\x81" + b"\x0f\x01" + b"\x19\x01" + EXIT_0

        # Act
        result = bsp.apply(b"abcd", b"\x08" + word(3) + program)

        # Assert
        assert result == b"\x00bcd"

    @pytest.mark.parametrize(
        "program",
        [
            b"\x60" + word(0xFFFFFFFF) + b"\x62" + word(1),
            b"\x64" + word(1),
            b"\x66" + word(5),
            b"\x60" + word(0xFFFFFFFF) + b"\x18\x00",
            b"\x60" + word(0xFFFFFFFF) + b"\x70" + word(2) + b"\x00",
            b"\x60" + word(0xFFFFFFFF) + b"\x7c" + word(0) + word(2),
        ],
        ids=["forward", "back", "end", "write", "fill", "data"],
    )
    def test_a_pointer_that_would_overflow_is_fatal(self, program):
        # Arrange
        source = b"abcd"

        # Act
        with pytest.raises(bspvm.BspError) as raised:
            bsp.apply(source, program + EXIT_0)

        # Assert
        assert "the current file pointer overflows" in str(raised.value)


class TestStackAndControl:
    @pytest.mark.parametrize(
        ("program", "message"),
        [
            (b"\x8c\x01" + word(0), "stack position 0x0 is outside the 0-value stack"),
            (b"\x8e" + word(0xFFFFFFFF), "popped an empty stack"),
            (b"\x83\x01", "read past the end"),
            (b"\x94\x01" + word(0) + word(0), "a nested patch of length 0"),
            (b"\x94\x01" + word(4) + word(100), "read past the end"),
            (b"\xa2" + word(0xD800), "not a Unicode character"),
            (b"\xa2" + word(0x110000), "not a Unicode character"),
            (b"\x68" + word(5), "runs past the end of the patch space"),
            (b"\x68" + word(5) + b"\xff\x00", "is not valid UTF-8"),
            (b"\x30\x01" + word(1) + word(0), "division by zero"),
            (b"\x6a\x01" + word(6) + word(14), "option list runs past the end"),
        ],
        ids=[
            "stack-read",
            "stack-shift",
            "jumptable",
            "empty-child",
            "child-past-end",
            "surrogate",
            "past-unicode",
            "unterminated",
            "utf8",
            "remainder",
            "unterminated-menu",
        ],
    )
    def test_a_bad_stack_or_control_operation_is_fatal(self, program, message):
        # Arrange
        source = b""

        # Act
        with pytest.raises(bspvm.BspError) as raised:
            bsp.apply(source, program)

        # Assert
        assert message in str(raised.value)

    def test_message_buffer_operations_print_what_they_build(self):
        # Arrange
        characters = b"\xa2" + word(0xE9) + b"\xa2" + word(0x10348) + b"\xa2" + word(0)
        program = characters + b"\xa4" + word(7) + b"\xa6" + b"\x06" + word(2)

        # Act
        with pytest.raises(bspvm.BspError) as raised:
            bsp.apply(b"", program)

        # Assert
        expected = "the patch exited with status 2: " + chr(0xE9) + chr(0x10348) + "7"
        assert str(raised.value) == expected

    @pytest.mark.parametrize(
        ("flags", "extra", "expected"),
        [
            (0x01, b"", 0x00000002),
            (0x21, b"", 0x40000000),
            (0x41, b"", 0x00000003),
            (0x61, b"", 0xC0000000),
            (0x80, b"\x02", 0x00000004),
        ],
        ids=["left", "right", "rotate", "arith", "variable-count"],
    )
    def test_each_shift_reads_its_own_operand_forms(self, flags, extra, expected):
        # Arrange
        value = word(0x80000001) if flags & 0x80 == 0 else b"\x03"
        setup = b"\x84\x03" + word(1) + b"\x84\x02" + word(2)
        program = setup + bytes([0xAB, flags, 0x01]) + value + extra + b"\x1d\x01" + EXIT_0

        # Act
        result = bsp.apply(b"", program)

        # Assert
        assert struct.unpack("<I", result)[0] == expected


class TestQuietInstructions:
    def test_nop_and_an_empty_write_change_nothing(self):
        # Arrange
        program = b"\x00" + b"\x60" + word(100) + b"\x7c" + word(0) + word(0) + EXIT_0

        # Act
        result = bsp.apply(b"ab", program)

        # Assert
        assert result == b"ab"
