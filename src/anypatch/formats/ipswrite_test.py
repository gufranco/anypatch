import struct

import pytest

from n64_save_patches import ipswrite

KNUTH = 2654435761


def image(size: int = 0x200) -> bytes:
    out = bytearray(size)
    for at in range(0, size - 3, 4):
        struct.pack_into(">I", out, at, (at * KNUTH) & 0xFFFFFFFF)
    return bytes(out)


def changed(before: bytes, at: int, data: bytes) -> bytes:
    out = bytearray(before)
    out[at : at + len(data)] = data
    return bytes(out)


def records(patch: bytes) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    at = len(ipswrite.MAGIC)
    while patch[at : at + 3] != ipswrite.END:
        offset = int.from_bytes(patch[at : at + 3], "big")
        size = int.from_bytes(patch[at + 3 : at + 5], "big")
        found = [*found, (offset, size)]
        at += 5 + (3 if size == 0 else size)
    return found


class TestTheFileShape:
    def test_a_patch_starts_with_patch_and_ends_with_eof(self):
        # Arrange
        before = image()

        # Act
        patch = ipswrite.build(before, changed(before, 0x40, b"\x00\x01"))

        # Assert
        assert patch.startswith(b"PATCH")
        assert patch.endswith(b"EOF")

    def test_two_identical_images_give_a_patch_with_no_records(self):
        # Arrange
        before = image()

        # Act
        patch = ipswrite.build(before, before)

        # Assert
        assert patch == b"PATCHEOF"

    def test_a_longer_target_is_reached_by_writing_past_the_end(self):
        # Arrange
        before = image(0x100)
        after = image(0x100) + bytes(range(0x40))

        # Act
        patch = ipswrite.build(before, after)

        # Assert
        assert records(patch) == [(0x100, 0x40)]
        assert ipswrite.apply(before, patch) == after

    def test_a_shorter_target_is_reached_with_the_size_after_eof(self):
        # Arrange
        before = image(0x200)
        after = before[:0x180]

        # Act
        patch = ipswrite.build(before, after)

        # Assert
        assert patch == b"PATCHEOF" + bytes([0x00, 0x01, 0x80])
        assert ipswrite.apply(before, patch) == after


class TestWhatThePatchReplays:
    def test_applying_a_built_patch_reproduces_the_target_exactly(self):
        # Arrange
        before = image()
        after = changed(changed(before, 0x10, b"\xde\xad"), 0x100, b"\xbe\xef\x01")

        # Act
        replayed = ipswrite.apply(before, ipswrite.build(before, after))

        # Assert
        assert replayed == after

    def test_a_long_fill_is_stored_as_a_run_record(self):
        # Arrange
        before = image(0x400)
        after = changed(before, 0x100, b"\xa5" * 0x100)

        # Act
        patch = ipswrite.build(before, after)

        # Assert
        assert records(patch) == [(0x100, 0)]
        assert ipswrite.apply(before, patch) == after

    def test_a_short_repeat_stays_a_literal_record(self):
        # Arrange
        before = image()
        after = changed(before, 0x20, b"\x00" * 3 + b"\x11")

        # Act
        patch = ipswrite.build(before, after)

        # Assert
        assert records(patch) == [(0x20, 4)]

    def test_a_change_longer_than_one_record_is_split_and_still_replays(self):
        # Arrange
        before = bytes(0x20000)
        after = image(0x20000)

        # Act
        patch = ipswrite.build(before, after)

        # Assert
        assert len(records(patch)) > 1
        assert all(size <= ipswrite.MAX_RECORD for _, size in records(patch))
        assert ipswrite.apply(before, patch) == after

    def test_a_fill_longer_than_one_record_is_split_and_still_replays(self):
        # Arrange
        before = bytes(0x20000)
        after = changed(before, 0x100, b"\x5a" * 0x18000)

        # Act
        patch = ipswrite.build(before, after)

        # Assert
        assert [size for _, size in records(patch)] == [0, 0]
        assert ipswrite.apply(before, patch) == after


class TestTheOffsetsIpsCannotWrite:
    def test_a_change_at_or_past_sixteen_mebibytes_is_refused(self):
        # Arrange
        before = bytes(ipswrite.LIMIT + 0x10)
        after = changed(before, ipswrite.LIMIT + 4, b"\x01")

        # Act
        with pytest.raises(ipswrite.IpsError) as raised:
            ipswrite.build(before, after)

        # Assert
        assert "APS" in str(raised.value)

    def test_a_literal_starting_at_the_eof_offset_starts_one_byte_earlier(self):
        # Arrange
        before = bytes(ipswrite.END_AS_OFFSET + 0x10)
        after = changed(before, ipswrite.END_AS_OFFSET, b"\x01\x02")

        # Act
        patch = ipswrite.build(before, after)

        # Assert
        assert records(patch) == [(ipswrite.END_AS_OFFSET - 1, 3)]
        assert ipswrite.apply(before, patch) == after

    def test_a_run_starting_at_the_eof_offset_becomes_a_literal_one_byte_earlier(self):
        # Arrange
        before = bytes(ipswrite.END_AS_OFFSET + 0x20)
        after = changed(before, ipswrite.END_AS_OFFSET, b"\x07" * 0x10)

        # Act
        patch = ipswrite.build(before, after)

        # Assert
        assert records(patch) == [(ipswrite.END_AS_OFFSET - 1, 0x11)]
        assert ipswrite.apply(before, patch) == after


class TestReadingAPatch:
    def test_a_file_without_the_magic_is_refused(self):
        # Arrange
        before = image()

        # Act
        with pytest.raises(ipswrite.IpsError) as raised:
            ipswrite.apply(before, b"NOTIPS")

        # Assert
        assert "PATCH" in str(raised.value)

    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            (b"PATCH\x00\x00", "ends inside the record"),
            (b"PATCH\x00\x00\x10\x00\x04ab", "ends inside the 4-byte record"),
            (b"PATCH\x00\x00\x10\x00\x00\x00", "ends inside the run record"),
            (b"PATCHEOFxx", "2 bytes follow EOF"),
        ],
    )
    def test_a_damaged_patch_is_refused_with_where_it_broke(self, patch, message):
        # Arrange
        before = image()

        # Act
        with pytest.raises(ipswrite.IpsError) as raised:
            ipswrite.apply(before, patch)

        # Assert
        assert message in str(raised.value)

    def test_a_record_past_the_end_pads_the_gap_with_zeros(self):
        # Arrange
        before = b"\x11" * 4
        patch = b"PATCH" + bytes([0, 0, 8, 0, 2]) + b"\xaa\xbb" + b"EOF"

        # Act
        after = ipswrite.apply(before, patch)

        # Assert
        assert after == b"\x11" * 4 + bytes(4) + b"\xaa\xbb"
