import struct

import pytest

from anypatch.formats import bsp, bspvm, imagesize


def word(value: int) -> bytes:
    return struct.pack("<I", value & 0xFFFFFFFF)


def run(
    program: bytes,
    source: bytes = b"",
    choices: tuple[int, ...] = (),
    limits: bspvm.Limits = bspvm.DEFAULT_LIMITS,
) -> bytes:
    return bsp.apply(source, program, choices=choices, limits=limits)


EXIT_0 = b"\x06" + word(0)


class TestTheMachine:
    def test_an_exit_with_status_zero_returns_the_file_buffer(self):
        # Arrange
        program = b"\x1c" + word(0x64636261) + EXIT_0

        # Act
        result = run(program, b"xyz")

        # Assert
        assert result == b"abcd"

    def test_a_return_with_an_empty_stack_exits_with_status_zero(self):
        # Arrange
        program = b"\x18\x41\x01"

        # Act
        result = run(program)

        # Assert
        assert result == b"A"

    def test_a_nested_patch_shares_the_file_and_hands_back_its_status(self):
        # Arrange
        child = b"\x18\x42" + b"\x06" + word(7)
        program = b"\x94\x05" + word(17) + word(len(child)) + b"\x19\x05" + EXIT_0 + child

        # Act
        result = run(program)

        # Assert
        assert result == b"B\x07"

    def test_a_menu_takes_the_next_choice_given(self):
        # Arrange
        labels = b"one\x00two\x00"
        table_at = 13
        options = word(table_at + 12) + word(table_at + 16) + word(0xFFFFFFFF)
        program = b"\x6a\x01" + word(table_at) + b"\x19\x01" + b"\x06" + word(0) + options + labels

        # Act
        result = run(program, choices=(1,))

        # Assert
        assert result == b"\x01"


class TestFailures:
    @pytest.mark.parametrize(
        ("program", "message"),
        [
            (b"\xff", "undefined opcode 0xff at 0x0"),
            (b"\x06\x00", "read past the end of the 2-byte patch space at 0x1"),
            (b"\x0a\x01", "popped an empty stack"),
            (b"\x0c\x01", "read past the end of the file buffer"),
            (b"\x06" + word(5), "the patch exited with status 5"),
            (b"\x2c\x01" + word(1) + word(0), "division by zero"),
            (b"\x02" + word(0), "ran past"),
        ],
        ids=["opcode", "patch-end", "empty-stack", "file-end", "status", "divide", "steps"],
    )
    def test_a_fatal_condition_stops_the_script(self, program, message):
        # Arrange
        limits = bspvm.Limits(steps=1000)

        # Act
        with pytest.raises(bspvm.BspError) as raised:
            run(program, limits=limits)

        # Assert
        assert message in str(raised.value)

    def test_a_failure_carries_the_last_message_the_script_printed(self):
        # Arrange
        program = b"\x68" + word(10) + b"\x06" + word(1) + b"wrong file\x00"

        # Act
        with pytest.raises(bspvm.BspError) as raised:
            run(program)

        # Assert
        assert str(raised.value) == "the patch exited with status 1: wrong file"

    def test_a_menu_without_a_choice_names_its_options(self):
        # Arrange
        options = word(15) + word(0xFFFFFFFF) + b"\x00"
        program = b"\x6a\x01" + word(6) + options + b"yes\x00"

        # Act
        with pytest.raises(bspvm.BspError) as raised:
            run(program)

        # Assert
        assert "the patch asks to choose between: yes" in str(raised.value)

    def test_a_choice_past_the_options_is_refused(self):
        # Arrange
        program = b"\x6a\x01" + word(6) + word(14) + word(0xFFFFFFFF) + b"yes\x00"

        # Act
        with pytest.raises(bspvm.BspError) as raised:
            run(program, choices=(3,))

        # Assert
        assert "choice 3 is past the 1 options" in str(raised.value)

    def test_the_stack_cannot_grow_past_its_limit(self):
        # Arrange
        program = b"\xa8" + word(5)

        # Act
        with pytest.raises(bspvm.BspError) as raised:
            run(program, limits=bspvm.Limits(stack=4))

        # Assert
        assert "the stack grows past 4 values" in str(raised.value)

    def test_nested_patches_cannot_nest_past_their_limit(self):
        # Arrange
        program = b"\x94\x01" + word(0) + word(10)

        # Act
        with pytest.raises(bspvm.BspError) as raised:
            run(program, limits=bspvm.Limits(depth=3))

        # Assert
        assert "nested patches past 3 levels" in str(raised.value)

    def test_a_write_past_the_ceiling_is_refused_before_allocating(self):
        # Arrange
        program = b"\x60" + word(imagesize.LIMIT) + b"\x18\x01" + EXIT_0

        # Act
        with pytest.raises(ValueError) as raised:
            run(program)

        # Assert
        assert "ceiling" in str(raised.value)
