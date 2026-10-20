import struct
import zlib

import pytest

from anypatch.formats import bps, imagesize, varint

BEFORE = b"ABCDEFGH"
AFTER = b"ABxDEFGH" + bytes(9)
BODY = b"BPS1\x88\x91\x80\x84\x81x\x90\x81\x00\x9f\x90"


def sealed(body: bytes, before: bytes = BEFORE, after: bytes = AFTER) -> bytes:
    checked = body + struct.pack("<II", zlib.crc32(before), zlib.crc32(after))
    return checked + struct.pack("<I", zlib.crc32(checked))


class TestBuilding:
    def test_a_worked_example_gives_the_exact_bytes(self):
        # Arrange
        before, after = BEFORE, AFTER

        # Act
        patch = bps.build(before, after)

        # Assert
        assert patch == sealed(BODY)

    def test_a_shrinking_change_round_trips(self):
        # Arrange
        before, after = b"ABCDEFGHIJKLMNOP", b"ABQDEF"
        patch = bps.build(before, after)

        # Act
        replayed = bps.apply(before, patch)

        # Assert
        assert replayed == after

    def test_a_change_mixing_literals_and_runs_round_trips(self):
        # Arrange
        before = bytes(range(64))
        after = before[:10] + b"xy" + b"\x07" * 20 + b"z" + before[33:] + b"\xff" * 12 + b"tail"
        patch = bps.build(before, after)

        # Act
        replayed = bps.apply(before, patch)

        # Assert
        assert replayed == after


class TestApplying:
    def test_the_worked_example_applies_to_its_source(self):
        # Arrange
        patch = sealed(BODY)

        # Act
        replayed = bps.apply(BEFORE, patch)

        # Assert
        assert replayed == AFTER

    def test_source_copies_move_both_ways(self):
        # Arrange
        body = b"BPS1\x84\x84\x80\x82\x86\x82\x85\x82\x85\x82\x85"
        patch = sealed(body, b"ABCD", b"DCBA")

        # Act
        replayed = bps.apply(b"ABCD", patch)

        # Assert
        assert replayed == b"DCBA"

    def test_a_target_copy_may_overlap_what_it_writes(self):
        # Arrange
        body = b"BPS1\x84\x87\x80\x85AB\x93\x80"
        patch = sealed(body, b"ABCD", b"ABABABA")

        # Act
        replayed = bps.apply(b"ABCD", patch)

        # Assert
        assert replayed == b"ABABABA"

    def test_metadata_is_skipped_and_reported(self):
        # Arrange
        body = b"BPS1\x84\x84\x83<m>\x8c"
        patch = sealed(body, b"ABCD", b"ABCD")

        # Act
        found = bps.metadata(patch)

        # Assert
        assert found == "<m>"
        assert bps.apply(b"ABCD", patch) == b"ABCD"

    def test_a_dump_that_already_carries_the_patch_comes_back_unchanged(self):
        # Arrange
        patch = sealed(BODY)

        # Act
        replayed = bps.apply(AFTER, patch)

        # Assert
        assert replayed == AFTER

    def test_another_dump_is_refused_naming_both_checksums(self):
        # Arrange
        patch = sealed(BODY)

        # Act
        with pytest.raises(bps.BpsError) as raised:
            bps.apply(b"ZZZZZZZZ", patch)

        # Assert
        wanted = f"{zlib.crc32(BEFORE):08X}"
        have = f"{zlib.crc32(b'ZZZZZZZZ'):08X}"
        assert str(raised.value) == (
            f"made for a 8-byte dump with CRC32 {wanted}, but this one is 8 bytes with CRC32 {have}"
        )

    def test_a_result_with_the_wrong_checksum_is_refused(self):
        # Arrange
        patch = sealed(BODY, BEFORE, AFTER[:-1] + b"\x01")

        # Act
        with pytest.raises(bps.BpsError) as raised:
            bps.apply(BEFORE, patch)

        # Assert
        assert "the patch expects" in str(raised.value)


class TestDamage:
    @pytest.mark.parametrize(
        ("body", "message"),
        [
            (b"BPS1\x84\x88\x80\x90", "past the end of the source"),
            (b"BPS1\x84\x84\x80\x82\x8a", "outside the source"),
            (b"BPS1\x84\x84\x80\x82\x83", "outside the source"),
            (b"BPS1\x84\x84\x80\x83\x80", "has not been written"),
            (b"BPS1\x84\x84\x80\x85AB\x83\x83", "has not been written"),
            (b"BPS1\x84\x82\x80\x8c", "past the 2-byte target"),
            (b"BPS1\x84\x84\x80\x84", "write 2 of 4 bytes"),
            (b"BPS1\x84\x84\x80\x8dAB", "ends inside"),
            (b"BPS1\x84\x84\x89ab", "ends inside"),
            (b"BPS1\x84\x84", "ends inside a number"),
            (b"BPS1\x84\x84\x80\x01", "ends inside a number"),
        ],
    )
    def test_a_damaged_action_list_is_refused(self, body, message):
        # Arrange
        patch = sealed(body, b"ABCD", b"ABCD")

        # Act
        with pytest.raises(bps.BpsError) as raised:
            bps.apply(b"ABCD", patch)

        # Assert
        assert message in str(raised.value)

    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            (b"UPS1" + bytes(14), "not a BPS patch"),
            (b"BPS1" + bytes(8), "too short"),
            (sealed(BODY)[:-1] + b"\x00", "damaged"),
        ],
    )
    def test_a_damaged_file_is_refused(self, patch, message):
        # Arrange
        source = BEFORE

        # Act
        with pytest.raises(bps.BpsError) as raised:
            bps.apply(source, patch)

        # Assert
        assert message in str(raised.value)


class TestTheSizeCeiling:
    def test_a_patch_claiming_a_huge_result_is_refused_before_allocating(self):
        # Arrange
        patch = sealed(b"BPS1\x88" + varint.encode(1 << 40) + b"\x80")

        # Act
        with pytest.raises(imagesize.ImageSizeError) as raised:
            bps.apply(BEFORE, patch)

        # Assert
        assert "ceiling" in str(raised.value)


class TestMetadataOnWrite:
    def test_a_description_is_carried_as_utf8_metadata_and_the_patch_still_applies(self):
        # Arrange
        before, after = b"source bytes", b"target bytes!"

        # Act
        patch = bps.build(before, after, description="Tradução v1")

        # Assert
        assert bps.metadata(patch) == "Tradução v1"
        assert bps.apply(before, patch) == after
