import struct

import pytest

from anypatch.formats import gdiff, imagesize

HEADER = b"\xd1\xff\xd1\xff\x04"


class TestTheSpecificationExample:
    def test_the_worked_example_rebuilds_the_new_file(self):
        # Arrange
        patch = HEADER + bytes([249, 0, 0, 2, 2]) + b"XY" + bytes([249, 0, 2, 2, 249, 0, 1, 4, 0])

        # Act
        result = gdiff.apply(b"ABCDEFG", patch)

        # Assert
        assert result == b"ABXYCDBCDE"


class TestEveryCommandForm:
    @pytest.mark.parametrize(
        ("command", "expected"),
        [
            (bytes([247]) + struct.pack(">H", 3) + b"abc", b"abc"),
            (bytes([248]) + struct.pack(">i", 2) + b"de", b"de"),
            (bytes([249]) + struct.pack(">HB", 1, 2), b"BC"),
            (bytes([250]) + struct.pack(">HH", 1, 2), b"BC"),
            (bytes([251]) + struct.pack(">Hi", 1, 2), b"BC"),
            (bytes([252]) + struct.pack(">iB", 2, 3), b"CDE"),
            (bytes([253]) + struct.pack(">iH", 2, 3), b"CDE"),
            (bytes([254]) + struct.pack(">ii", 2, 3), b"CDE"),
            (bytes([255]) + struct.pack(">qi", 4, 2), b"EF"),
        ],
    )
    def test_each_form_reads_its_own_widths(self, command, expected):
        # Arrange
        patch = HEADER + command + b"\x00"

        # Act
        result = gdiff.apply(b"ABCDEFG", patch)

        # Assert
        assert result == expected


class TestWriting:
    def test_unchanged_runs_are_copied_and_changes_are_data(self):
        # Arrange
        before = bytes(range(16))
        after = before[:4] + b"\xaa" + before[5:] + b"tail"

        # Act
        patch = gdiff.build(before, after)

        # Assert
        assert patch == (
            HEADER
            + bytes([249, 0, 0, 4])
            + bytes([1, 0xAA])
            + bytes([249, 0, 5, 11])
            + bytes([4])
            + b"tail"
            + b"\x00"
        )

    @pytest.mark.parametrize(
        ("before", "after"),
        [
            (bytes(range(256)) * 300, bytes(range(256)) * 290 + b"\x01" * 300),
            (bytes(0x20000), bytes(0x10000) + b"\x05" * 0x11000),
            (b"short", b""),
            (b"", b"grown from nothing"),
        ],
    )
    def test_a_change_round_trips(self, before, after):
        # Arrange
        patch = gdiff.build(before, after)

        # Act
        result = gdiff.apply(before, patch)

        # Assert
        assert result == after

    def test_a_copy_past_64_kib_uses_a_four_byte_position(self):
        # Arrange
        before = bytes(0x20000)
        after = before[:0x10001] + b"\x01" + before[0x10002:0x10100]

        # Act
        patch = gdiff.build(before, after)

        # Assert
        assert bytes([252]) + struct.pack(">iB", 0x10002, 0xFE) in patch

    def test_a_long_copy_and_a_long_literal_take_the_wide_forms(self):
        # Arrange
        before = bytes(0x20000)
        after = before + bytes([1, 2, 3]) * 0x6000

        # Act
        patch = gdiff.build(before, after)

        # Assert
        assert bytes([251]) + struct.pack(">Hi", 0, 0x20000) in patch
        assert bytes([248]) + struct.pack(">i", 0x12000) in patch


class TestDamage:
    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            (b"BSDIFF40", "not a GDIFF patch"),
            (b"\xd1\xff\xd1\xff\x05\x00", "version 5"),
            (HEADER, "ends before its EOF command"),
            (HEADER + bytes([3]) + b"ab", "ends inside the 3-byte data"),
            (HEADER + bytes([250, 0]), "ends inside the command at byte 5"),
            (
                HEADER + bytes([249, 0, 6, 2, 0]),
                "copy of 2 bytes from 6 reaches past the 7-byte source",
            ),
            (HEADER + bytes([248]) + struct.pack(">i", -1) + b"\x00", "a negative length"),
            (HEADER + bytes([0, 1]), "1 bytes follow the EOF command"),
        ],
    )
    def test_a_damaged_patch_is_refused(self, patch, message):
        # Arrange
        source = b"ABCDEFG"

        # Act
        with pytest.raises(gdiff.GdiffError) as raised:
            gdiff.apply(source, patch)

        # Assert
        assert message in str(raised.value)

    def test_copies_that_add_up_past_the_ceiling_are_refused(self):
        # Arrange
        source = bytes(0x10000)
        copy = bytes([250]) + struct.pack(">HH", 0, 0xFFFF)
        patch = HEADER + copy * ((imagesize.LIMIT // 0xFFFF) + 2) + b"\x00"

        # Act
        with pytest.raises(imagesize.ImageSizeError) as raised:
            gdiff.apply(source, patch)

        # Assert
        assert "ceiling" in str(raised.value)


class TestCopiesPastTwoGibibytes:
    def test_a_position_past_the_signed_32_bit_range_uses_the_long_form(self):
        # Arrange
        position = 1 << 32

        # Act
        command = gdiff.copy(position, 5)

        # Assert
        assert command == bytes([255]) + struct.pack(">qi", 1 << 32, 5)

    def test_a_length_past_the_signed_32_bit_range_is_split(self):
        # Arrange
        length = gdiff.INT + 10

        # Act
        command = gdiff.copy(0, length)

        # Assert
        assert command == (
            bytes([251])
            + struct.pack(">Hi", 0, gdiff.INT)
            + bytes([252])
            + struct.pack(">iB", gdiff.INT, 10)
        )


class TestAChangeAtTheFirstByte:
    def test_it_starts_with_data_rather_than_a_copy(self):
        # Arrange
        before = bytes(range(16))
        after = b"\xff" + before[1:]

        # Act
        patch = gdiff.build(before, after)

        # Assert
        assert patch[5:7] == bytes([1, 0xFF])
        assert gdiff.apply(before, patch) == after


class TestTheSmallestCopyForm:
    @pytest.mark.parametrize(
        ("position", "length", "expected"),
        [
            (0x10, 0x20, bytes([249]) + struct.pack(">HB", 0x10, 0x20)),
            (0x10, 0x200, bytes([250]) + struct.pack(">HH", 0x10, 0x200)),
            (0x10, 0x20000, bytes([251]) + struct.pack(">Hi", 0x10, 0x20000)),
            (0x10000, 0x20, bytes([252]) + struct.pack(">iB", 0x10000, 0x20)),
            (0x10000, 0x200, bytes([253]) + struct.pack(">iH", 0x10000, 0x200)),
            (0x10000, 0x20000, bytes([254]) + struct.pack(">ii", 0x10000, 0x20000)),
        ],
    )
    def test_each_position_and_length_picks_its_form(self, position, length, expected):
        # Arrange
        where = position

        # Act
        command = gdiff.copy_command(where, length)

        # Assert
        assert command == expected
