import struct

import pytest

from anypatch.formats import dps

SOURCE = b"ABCDEFGHIJKLMNOP"


def header(size: int = len(SOURCE), version: int = 1, name: bytes = b"") -> bytes:
    fields = name.ljust(64, b"\x00") + bytes(64) + bytes(64)
    return fields + bytes([0, version]) + struct.pack("<I", size)


def copy(out_at: int, in_at: int, length: int) -> bytes:
    return struct.pack("<BIII", dps.COPY, out_at, in_at, length)


def data(out_at: int, payload: bytes) -> bytes:
    return struct.pack("<BII", dps.DATA, out_at, len(payload)) + payload


class TestReading:
    def test_copies_and_enclosed_data_build_the_output(self):
        # Arrange
        patch = header() + copy(0, 0, 2) + data(2, b"xy") + copy(4, 4, 12) + data(16, b"!!")

        # Act
        result = dps.apply(SOURCE, patch)

        # Assert
        assert result == b"ABxyEFGHIJKLMNOP!!"

    def test_a_copy_may_take_bytes_from_anywhere_in_the_source(self):
        # Arrange
        patch = header() + copy(0, 8, 4) + copy(4, 0, 4)

        # Act
        result = dps.apply(SOURCE, patch)

        # Assert
        assert result == b"IJKLABCD"

    def test_the_output_is_only_what_the_records_write(self):
        # Arrange
        patch = header()

        # Act
        result = dps.apply(SOURCE, patch)

        # Assert
        assert result == b""


class TestRefusals:
    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            (header()[:100], "too short to hold the 198-byte DPS header"),
            (header(version=2), "DPS version 2; only 1 is read"),
            (header(size=99), "made for a 99-byte source, but this one is 16 bytes"),
            (header() + b"\x07" + bytes(8), "unknown record mode 7 at byte 198"),
            (header() + copy(0, 10, 10), "copies 10 bytes from 0xa, past the 16-byte source"),
            (header() + data(0, b"abc")[:-1], "the patch ends inside the record at byte 198"),
            (header() + b"\x00\x01", "the patch ends inside the record at byte 198"),
        ],
        ids=["short", "version", "size", "mode", "copy-past-end", "short-data", "short-copy"],
    )
    def test_a_damaged_or_mismatched_patch_is_refused(self, patch, message):
        # Arrange
        source = SOURCE

        # Act
        with pytest.raises(dps.DpsError) as raised:
            dps.apply(source, patch)

        # Assert
        assert message in str(raised.value)

    def test_a_patch_writing_past_the_ceiling_is_refused_before_allocating(self):
        # Arrange
        patch = header() + struct.pack("<BII", dps.DATA, 1 << 31, 1) + b"x"

        # Act
        with pytest.raises(ValueError) as raised:
            dps.apply(SOURCE, patch)

        # Assert
        assert "ceiling" in str(raised.value)


class TestWriting:
    def test_unchanged_spans_are_copied_and_changes_are_enclosed(self):
        # Arrange
        after = b"ABxyEFGHIJKLMNOP!!"

        # Act
        patch = dps.build(SOURCE, after, description="fix")

        # Assert
        assert patch == (
            header(name=b"fix") + copy(0, 0, 2) + data(2, b"xy") + copy(4, 4, 12) + data(16, b"!!")
        )

    @pytest.mark.parametrize(
        "after",
        [b"", b"AB", SOURCE, SOURCE[::-1], SOURCE + b"tail"],
        ids=["empty", "shrink", "same", "reversed", "grow"],
    )
    def test_a_written_patch_rebuilds_its_target(self, after):
        # Arrange
        patch = dps.build(SOURCE, after)

        # Act
        result = dps.apply(SOURCE, patch)

        # Assert
        assert result == after

    def test_a_long_name_is_cut_to_its_field(self):
        # Arrange
        description = "n" * 100

        # Act
        patch = dps.build(SOURCE, SOURCE, description=description)

        # Assert
        assert patch[:64] == b"n" * 64
        assert patch[64] == 0
