import pytest

from anypatch.formats import imagesize, jojodiff

SOURCE = b"ABCDEFGHIJKLMNOP"
TARGET = b"ABxyEFGHIJKLMNOP!!"
ESC, MOD, INS, DEL, EQL, BKT = b"\xa7", b"\xa6", b"\xa5", b"\xa4", b"\xa3", b"\xa2"


class TestReading:
    @pytest.mark.parametrize(
        ("patch", "expected"),
        [
            (
                ESC + EQL + b"\x01" + ESC + MOD + b"xy" + ESC + EQL + b"\x0b" + ESC + INS + b"!!",
                TARGET,
            ),
            (b"xy" + ESC + EQL + b"\x01", b"xyCD"),
            (ESC + EQL + b"\x00" + b"xy", b"Axy"),
            (ESC + DEL + b"\x03" + ESC + EQL + b"\x01", b"EF"),
            (ESC + EQL + b"\x03" + ESC + BKT + b"\x01" + ESC + EQL + b"\x00", b"ABCDC"),
            (ESC + INS + b"ab" + ESC + EQL + b"\x00", b"abA"),
            (ESC + MOD + b"ab" + ESC + EQL + b"\x00", b"abC"),
            (b"", b""),
        ],
        ids=[
            "explicit-ops",
            "default-mod-at-start",
            "default-mod-after-a-length",
            "delete",
            "backtrace",
            "insert-keeps-the-source-position",
            "modify-moves-the-source-position",
            "empty",
        ],
    )
    def test_each_operation_moves_the_source_and_output_as_jpatch_does(self, patch, expected):
        # Arrange
        source = SOURCE

        # Act
        result = jojodiff.apply(source, patch)

        # Assert
        assert result == expected

    @pytest.mark.parametrize(
        ("patch", "expected"),
        [
            (ESC + MOD + ESC + ESC, ESC),
            (ESC + MOD + ESC + MOD, ESC + MOD),
            (ESC + INS + ESC + INS, ESC + INS),
            (ESC + MOD + ESC + b"z", ESC + b"z"),
            (ESC + b"z", ESC + b"z"),
            (ESC + ESC + b"q", ESC + b"q"),
        ],
        ids=[
            "doubled-escape",
            "escape-before-the-current-mod",
            "escape-before-the-current-ins",
            "escape-before-plain-data",
            "pending-escape-at-the-start",
            "pending-doubled-escape-at-the-start",
        ],
    )
    def test_escape_bytes_in_data_are_read_as_jpatch_reads_them(self, patch, expected):
        # Arrange
        source = SOURCE

        # Act
        result = jojodiff.apply(source, patch)

        # Assert
        assert result == expected

    @pytest.mark.parametrize(
        ("encoded", "length"),
        [
            (b"\xfb", 252),
            (b"\xfc\x00", 253),
            (b"\xfc\xff", 508),
            (b"\xfd\x00\x05", 5),
            (b"\xfe\x00\x00\x00\x07", 7),
            (b"\xff\x00\x00\x00\x00\x00\x00\x00\x09", 9),
        ],
        ids=["byte", "byte-plus-253-low", "byte-plus-253-high", "word", "dword", "qword"],
    )
    def test_every_length_form_is_read(self, encoded, length):
        # Arrange
        source = bytes(range(256)) * 2

        # Act
        result = jojodiff.apply(source, ESC + EQL + encoded)

        # Assert
        assert result == source[:length]


class TestRefusals:
    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            (ESC, "the patch ends after an escape byte"),
            (ESC + MOD + b"ab" + ESC, "the patch ends after an escape byte"),
            (ESC + EQL, "the patch ends inside a length"),
            (ESC + EQL + b"\xfd\x01", "the patch ends inside a length"),
            (ESC + EQL + b"\x10", "copies 17 bytes from 0x0, past the 16-byte source"),
            (ESC + BKT + b"\x00", "goes back 1 bytes from 0x0, before the start of the source"),
        ],
        ids=[
            "lone-escape",
            "escape-at-end",
            "no-length",
            "short-length",
            "past-end",
            "before-start",
        ],
    )
    def test_a_damaged_patch_is_refused(self, patch, message):
        # Arrange
        source = SOURCE

        # Act
        with pytest.raises(jojodiff.JojodiffError) as raised:
            jojodiff.apply(source, patch)

        # Assert
        assert message in str(raised.value)

    def test_repeated_copies_past_the_ceiling_are_refused_before_allocating(self):
        # Arrange
        source = bytes(1 << 16)
        again = ESC + EQL + b"\xfe\x00\x01\x00\x00" + ESC + BKT + b"\xfe\x00\x01\x00\x00"
        patch = again * ((imagesize.LIMIT >> 16) + 1)

        # Act
        with pytest.raises(ValueError) as raised:
            jojodiff.apply(source, patch)

        # Assert
        assert "ceiling" in str(raised.value)


class TestWriting:
    def test_unchanged_runs_are_copied_and_changes_are_modified_or_inserted(self):
        # Arrange
        after = TARGET

        # Act
        patch = jojodiff.build(SOURCE, after)

        # Assert
        assert patch == (
            ESC + EQL + b"\x01" + ESC + MOD + b"xy" + ESC + EQL + b"\x0b" + ESC + INS + b"!!"
        )

    def test_an_escape_byte_in_the_data_is_doubled(self):
        # Arrange
        after = b"A" + ESC + MOD + SOURCE[3:]

        # Act
        patch = jojodiff.build(SOURCE, after)

        # Assert
        assert patch == ESC + EQL + b"\x00" + ESC + MOD + ESC + ESC + MOD + ESC + EQL + b"\x0c"

    @pytest.mark.parametrize(
        ("length", "encoded"),
        [
            (252, b"\xfb"),
            (253, b"\xfc\x00"),
            (508, b"\xfc\xff"),
            (509, b"\xfd\x01\xfd"),
            (65535, b"\xfd\xff\xff"),
            (65536, b"\xfe\x00\x01\x00\x00"),
        ],
        ids=["byte", "plus-low", "plus-high", "word-low", "word-high", "dword"],
    )
    def test_each_length_takes_the_shortest_form(self, length, encoded):
        # Arrange
        before = bytes(length)

        # Act
        patch = jojodiff.build(before, before + b"\x01")

        # Assert
        assert patch == ESC + EQL + encoded + ESC + INS + b"\x01"

    @pytest.mark.parametrize(
        "after",
        [b"", b"AB", SOURCE, SOURCE[::-1], SOURCE + b"tail", ESC * 3 + SOURCE + ESC + EQL],
        ids=["empty", "shrink", "same", "reversed", "grow", "escapes"],
    )
    def test_a_written_patch_rebuilds_its_target(self, after):
        # Arrange
        patch = jojodiff.build(SOURCE, after)

        # Act
        result = jojodiff.apply(SOURCE, patch)

        # Assert
        assert result == after

    def test_a_length_past_32_bits_takes_the_64_bit_form(self):
        # Arrange
        length = 1 << 32

        # Act
        encoded = jojodiff.length_code(length)

        # Assert
        assert encoded == b"\xff\x00\x00\x00\x01\x00\x00\x00\x00"
