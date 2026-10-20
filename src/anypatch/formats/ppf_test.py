import struct

import pytest

from n64_save_patches import imagesize, ppf

TITLE = b"t" + b" " * 49
WORKED = (
    b"PPF30\x02"
    + TITLE
    + b"\x00\x00\x01\x00"
    + struct.pack("<QB", 1, 1)
    + b"XB"
    + struct.pack("<QB", 4, 1)
    + b"E\x00"
)
SOURCE = bytes(range(256)) * 0x98


def ppf3(records: bytes, *, undo: bool = False, block: bytes | None = None, kind: int = 0) -> bytes:
    flags = bytes([kind, block is not None, undo, 0])
    return b"PPF30\x02" + TITLE + flags + (block or b"") + records


def ppf2(records: bytes, size: int, block: bytes) -> bytes:
    return b"PPF20\x01" + TITLE + struct.pack("<I", size) + block + records


class TestBuilding:
    def test_a_worked_example_gives_the_exact_bytes(self):
        # Arrange
        before, after = b"ABCD", b"AXCDE"

        # Act
        patch = ppf.build(before, after, description="t")

        # Assert
        assert patch == WORKED

    def test_a_growth_ending_in_zeros_still_reaches_the_full_size(self):
        # Arrange
        before, after = b"AB", b"AB\x00\x00"
        patch = ppf.build(before, after)

        # Act
        replayed = ppf.apply(before, patch)

        # Assert
        assert replayed == after

    def test_a_change_longer_than_one_record_is_split(self):
        # Arrange
        before, after = bytes(300), b"\x01" * 300
        patch = ppf.build(before, after)

        # Act
        replayed = ppf.apply(before, patch)

        # Assert
        assert replayed == after
        assert len(patch) == 60 + 2 * 9 + 2 * 300

    def test_a_shrinking_change_is_refused(self):
        # Arrange
        before, after = b"ABCD", b"AB"

        # Act
        with pytest.raises(ppf.PpfError) as raised:
            ppf.build(before, after)

        # Assert
        assert "cannot shrink" in str(raised.value)


class TestApplying:
    def test_the_worked_example_applies_to_its_source(self):
        # Arrange
        source = b"ABCD"

        # Act
        replayed = ppf.apply(source, WORKED)

        # Assert
        assert replayed == b"AXCDE"

    def test_a_dump_that_already_carries_the_patch_comes_back_unchanged(self):
        # Arrange
        source = b"AXCDE"

        # Act
        replayed = ppf.apply(source, WORKED)

        # Assert
        assert replayed == source

    def test_bytes_that_are_neither_original_nor_patched_are_refused(self):
        # Arrange
        source = b"AQCD"

        # Act
        with pytest.raises(ppf.PpfError) as raised:
            ppf.apply(source, WORKED)

        # Assert
        assert str(raised.value) == (
            "at 0x1 this dump holds 51, which is neither the original 42 nor the patched 58"
        )

    def test_a_version_one_patch_overwrites_without_checks(self):
        # Arrange
        patch = b"PPF10\x00" + TITLE + struct.pack("<IB", 1, 1) + b"X"

        # Act
        replayed = ppf.apply(b"ABCD", patch)

        # Assert
        assert replayed == b"AXCD"

    def test_a_version_two_patch_checks_size_and_block(self):
        # Arrange
        block = SOURCE[0x9320 : 0x9320 + 1024]
        patch = ppf2(struct.pack("<IB", 2, 1) + b"Z", len(SOURCE), block)

        # Act
        replayed = ppf.apply(SOURCE, patch)

        # Assert
        assert replayed == SOURCE[:2] + b"Z" + SOURCE[3:]

    def test_a_version_two_patch_for_another_size_is_refused(self):
        # Arrange
        block = SOURCE[0x9320 : 0x9320 + 1024]
        patch = ppf2(b"", len(SOURCE) + 1, block)

        # Act
        with pytest.raises(ppf.PpfError) as raised:
            ppf.apply(SOURCE, patch)

        # Assert
        assert str(raised.value) == "made for a 38,913-byte image, but this one is 38,912 bytes"

    def test_a_version_three_gi_block_check_is_read_at_its_own_offset(self):
        # Arrange
        block = SOURCE[0x80A0 : 0x80A0 + 1024]
        patch = ppf3(struct.pack("<QB", 0, 1) + b"Q", block=block, kind=1)

        # Act
        replayed = ppf.apply(SOURCE, patch)

        # Assert
        assert replayed == b"Q" + SOURCE[1:]

    def test_a_block_check_that_does_not_match_is_refused(self):
        # Arrange
        patch = ppf3(b"", block=bytes(1024))

        # Act
        with pytest.raises(ppf.PpfError) as raised:
            ppf.apply(SOURCE, patch)

        # Assert
        assert "block check at 0x9320" in str(raised.value)

    def test_a_file_id_diz_after_the_records_is_skipped(self):
        # Arrange
        diz = b"@BEGIN_FILE_ID.DIZhello@END_FILE_ID.DIZ" + struct.pack("<I", 5)
        patch = ppf3(struct.pack("<QB", 0, 1) + b"Q" + diz)

        # Act
        replayed = ppf.apply(b"ABCD", patch)

        # Assert
        assert replayed == b"QBCD"


class TestDamage:
    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            (b"IPS30\x02" + TITLE, "not a PPF patch"),
            (b"PPF30\x02", "too short"),
            (b"PPF30\x01" + TITLE + bytes(4), "version"),
            (b"PPF40\x03" + TITLE + bytes(4), "version"),
            (b"PPF30\x02" + TITLE + b"\x00", "ends inside its header"),
            (b"PPF20\x01" + TITLE + bytes(4) + bytes(10), "ends inside its header"),
            (b"PPF30\x02" + TITLE + b"\x00\x01\x00\x00" + bytes(10), "ends inside its header"),
            (ppf3(b"\x00\x00\x00"), "ends inside the record"),
            (ppf3(struct.pack("<QB", 0, 4) + b"AB"), "ends inside the record"),
            (ppf3(b"@BEGIN_FILE_ID.DIZhello"), "FILE_ID.DIZ"),
        ],
    )
    def test_a_damaged_patch_is_refused(self, patch, message):
        # Arrange
        source = b"ABCD"

        # Act
        with pytest.raises(ppf.PpfError) as raised:
            ppf.apply(source, patch)

        # Assert
        assert message in str(raised.value)


class TestTheSizeCeiling:
    def test_a_patch_claiming_a_huge_result_is_refused_before_allocating(self):
        # Arrange
        patch = ppf3(struct.pack("<QB", 1 << 40, 1) + b"x")

        # Act
        with pytest.raises(imagesize.ImageSizeError) as raised:
            ppf.apply(b"ABCD", patch)

        # Assert
        assert "ceiling" in str(raised.value)
