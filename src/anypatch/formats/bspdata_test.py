import struct

import pytest

from anypatch.formats import bsp, bspvm


def word(value: int) -> bytes:
    return struct.pack("<I", value & 0xFFFFFFFF)


EXIT_0 = b"\x06" + word(0)


class TestDataOperations:
    def test_xordata_past_the_end_writes_the_rest(self):
        # Arrange
        program = b"\x60" + word(2) + b"\x6c" + word(19) + word(4) + EXIT_0 + b"\x01\x01\x01\x01"

        # Act
        result = bsp.apply(b"abc", program)

        # Assert
        assert result == b"abb\x01\x01\x01"

    def test_xordata_from_past_the_end_only_writes(self):
        # Arrange
        program = b"\x60" + word(5) + b"\x6c" + word(19) + word(2) + EXIT_0 + b"\x07\x08"

        # Act
        result = bsp.apply(b"abc", program)

        # Assert
        assert result == b"abc\x00\x00\x07\x08"

    @pytest.mark.parametrize(
        ("program", "expected"),
        [
            (b"\x70" + word(0) + b"\x41", b"ab"),
            (b"\x74" + word(1) + b"\x41\x42", b"AB"),
            (b"\x78" + word(1) + word(0x44434241), b"ABCD"),
        ],
        ids=["no-bytes", "halfword", "word"],
    )
    def test_fills_write_their_count_of_values(self, program, expected):
        # Arrange
        source = b"ab"

        # Act
        result = bsp.apply(source, program + EXIT_0)

        # Assert
        assert result == expected

    def test_an_embedded_ips_patch_writes_relative_to_the_pointer(self):
        # Arrange
        ips = b"PATCH" + b"\x00\x00\x01\x00\x02hi" + b"\x00\x00\x04\x00\x00\x00\x02z" + b"EOF"
        program = b"\x60" + word(1) + b"\x86\x01" + word(16) + EXIT_0 + ips

        # Act
        result = bsp.apply(b"abcdefgh", program)

        # Assert
        assert result == b"abhiezzh"

    @pytest.mark.parametrize(
        ("ips", "message"),
        [
            (b"PATCX", "has no PATCH header"),
            (b"PATCH\x00\x00", "ends before its EOF"),
            (b"PATCH\xff\xff\xff\x00\x01x", "the current file pointer overflows"),
        ],
        ids=["header", "no-eof", "overflow"],
    )
    def test_a_broken_embedded_ips_patch_is_fatal(self, ips, message):
        # Arrange
        program = b"\x60" + word(0xFFFFFF00) + b"\x86\x01" + word(16) + EXIT_0 + ips

        # Act
        with pytest.raises(bspvm.BspError) as raised:
            bsp.apply(b"", program)

        # Assert
        assert message in str(raised.value)
