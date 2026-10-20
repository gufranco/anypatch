import binascii
import struct

import pytest

from anypatch.formats import apsgba, imagesize

BLOCK = 0x10000
SOURCE = bytes(range(256)) * 0x101


def crc16(data: bytes) -> int:
    return binascii.crc_hqx(data, 0xFFFF)


def block(data: bytes, at: int) -> bytes:
    return data[at : at + BLOCK].ljust(BLOCK, b"\x00")


def patch_for(before: bytes, after: bytes, offsets: list[int]) -> bytes:
    records = b"".join(
        struct.pack("<IHH", at, crc16(block(before, at)), crc16(block(after, at)))
        + bytes(x ^ y for x, y in zip(block(before, at), block(after, at), strict=True))
        for at in offsets
    )
    return b"APS1" + struct.pack("<II", len(before), len(after)) + records


def edited(data: bytes, at: int, new: bytes) -> bytes:
    return data[:at] + new + data[at + len(new) :]


AFTER = edited(edited(SOURCE, 10, b"\xaa\xbb"), BLOCK + 3, b"\xcc")
PATCH = patch_for(SOURCE, AFTER, [0, BLOCK])


class TestTheChecksum:
    def test_it_is_crc16_ccitt_false(self):
        # Arrange
        data = b"123456789"

        # Act
        found = apsgba.crc16(data)

        # Assert
        assert found == 0x29B1


class TestDetecting:
    @pytest.mark.parametrize(
        ("patch", "expected"),
        [
            (PATCH, True),
            (b"APS10" + bytes(len(PATCH) - 5), False),
            (PATCH[:-1], False),
            (b"APS1" + bytes(8), False),
        ],
    )
    def test_only_the_gba_layout_matches(self, patch, expected):
        # Arrange
        candidate = patch

        # Act
        found = apsgba.matches(candidate)

        # Assert
        assert found is expected


class TestApplying:
    def test_records_xor_their_blocks(self):
        # Arrange
        source = SOURCE

        # Act
        replayed = apsgba.apply(source, PATCH)

        # Assert
        assert replayed == AFTER

    def test_a_dump_that_already_carries_the_patch_comes_back_unchanged(self):
        # Arrange
        source = AFTER

        # Act
        replayed = apsgba.apply(source, PATCH)

        # Assert
        assert replayed == AFTER

    @pytest.mark.parametrize("size", [BLOCK + 9, 3 * BLOCK])
    def test_the_target_takes_its_recorded_size(self, size):
        # Arrange
        after = (AFTER + bytes(size))[:size]
        patch = patch_for(SOURCE, after, [0, BLOCK])

        # Act
        replayed = apsgba.apply(SOURCE, patch)

        # Assert
        assert replayed == after

    def test_a_dump_of_another_size_is_refused(self):
        # Arrange
        source = SOURCE[:-1]

        # Act
        with pytest.raises(apsgba.ApsGbaError) as raised:
            apsgba.apply(source, PATCH)

        # Assert
        assert str(raised.value) == "made for a 65,792-byte dump, but this one is 65,791 bytes"

    def test_a_block_that_differs_from_the_source_is_refused(self):
        # Arrange
        source = edited(SOURCE, BLOCK + 50, b"\x00")

        # Act
        with pytest.raises(apsgba.ApsGbaError) as raised:
            apsgba.apply(source, PATCH)

        # Assert
        wanted = crc16(block(SOURCE, BLOCK))
        have = crc16(block(source, BLOCK))
        assert str(raised.value) == (
            f"the block at 0x10000 has CRC16 {have:04X}; the patch expects {wanted:04X}"
        )

    def test_a_record_whose_result_has_the_wrong_checksum_is_refused(self):
        # Arrange
        patch = PATCH[:-1] + bytes([PATCH[-1] ^ 1])

        # Act
        with pytest.raises(apsgba.ApsGbaError) as raised:
            apsgba.apply(SOURCE, patch)

        # Assert
        assert "the patched block at 0x10000 has CRC16" in str(raised.value)

    def test_a_patch_without_the_gba_layout_is_refused(self):
        # Arrange
        patch = PATCH[:-1]

        # Act
        with pytest.raises(apsgba.ApsGbaError) as raised:
            apsgba.apply(SOURCE, patch)

        # Assert
        assert "not a GBA APS patch" in str(raised.value)


class TestTheSizeCeiling:
    def test_a_patch_claiming_a_huge_result_is_refused_before_allocating(self):
        # Arrange
        patch = b"APS1" + struct.pack("<II", len(SOURCE), 0x50000000) + PATCH[12:]

        # Act
        with pytest.raises(imagesize.ImageSizeError) as raised:
            apsgba.apply(SOURCE, patch)

        # Assert
        assert "ceiling" in str(raised.value)


class TestWriting:
    def test_only_the_blocks_that_change_are_recorded(self):
        # Arrange
        before, after = SOURCE, AFTER

        # Act
        patch = apsgba.build(before, after)

        # Assert
        assert patch == PATCH

    def test_a_target_that_grows_past_the_source_round_trips(self):
        # Arrange
        after = SOURCE + bytes(range(256)) * 300

        # Act
        patch = apsgba.build(SOURCE, after)

        # Assert
        assert apsgba.apply(SOURCE, patch) == after

    def test_a_target_that_shrinks_round_trips(self):
        # Arrange
        after = edited(SOURCE, 5, b"\x01")[: BLOCK + 9]

        # Act
        patch = apsgba.build(SOURCE, after)

        # Assert
        assert apsgba.apply(SOURCE, patch) == after

    def test_identical_files_cannot_make_a_patch_the_format_can_hold(self):
        # Arrange
        before = SOURCE

        # Act
        with pytest.raises(apsgba.ApsGbaError) as raised:
            apsgba.build(before, before)

        # Assert
        assert (
            str(raised.value) == "the files are identical, and an APS for GBA patch needs a record"
        )
