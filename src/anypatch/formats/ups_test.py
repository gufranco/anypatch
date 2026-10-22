import struct
import zlib

import pytest

from anypatch.formats import imagesize, ups, varint

BEFORE = b"ABCD"
AFTER = b"AXCDE"
BODY = b"UPS1\x84\x85\x81\x1a\x00\x81\x45\x00"


def sealed(body: bytes, before: bytes = BEFORE, after: bytes = AFTER) -> bytes:
    checked = body + struct.pack("<II", zlib.crc32(before), zlib.crc32(after))
    return checked + struct.pack("<I", zlib.crc32(checked))


class TestBuilding:
    def test_a_worked_example_gives_the_exact_bytes(self):
        # Arrange
        before, after = BEFORE, AFTER

        # Act
        patch = ups.build(before, after)

        # Assert
        assert patch == sealed(BODY)

    def test_a_shrinking_change_round_trips(self):
        # Arrange
        before, after = b"ABCDEFGH", b"ABxD"
        patch = ups.build(before, after)

        # Act
        replayed = ups.apply(before, patch)

        # Assert
        assert replayed == after

    def test_identical_images_give_a_patch_with_no_hunks(self):
        # Arrange
        before = BEFORE

        # Act
        patch = ups.build(before, before)

        # Assert
        assert patch == sealed(b"UPS1\x84\x84", before, before)


class TestApplying:
    def test_the_worked_example_applies_to_its_source(self):
        # Arrange
        patch = sealed(BODY)

        # Act
        replayed = ups.apply(BEFORE, patch)

        # Assert
        assert replayed == AFTER

    def test_a_image_that_already_carries_the_patch_comes_back_unchanged(self):
        # Arrange
        patch = sealed(BODY)

        # Act
        replayed = ups.apply(AFTER, patch)

        # Assert
        assert replayed == AFTER

    def test_another_image_is_refused_naming_both_checksums(self):
        # Arrange
        patch = sealed(BODY)

        # Act
        with pytest.raises(ups.UpsError) as raised:
            ups.apply(b"ZZZZ", patch)

        # Assert
        wanted = f"{zlib.crc32(BEFORE):08X}"
        have = f"{zlib.crc32(b'ZZZZ'):08X}"
        assert str(raised.value) == (
            f"made for a 4-byte image with CRC32 {wanted}, "
            f"but this one is 4 bytes with CRC32 {have}"
        )

    def test_a_result_with_the_wrong_checksum_is_refused(self):
        # Arrange
        patch = sealed(BODY, BEFORE, b"AXCDF")

        # Act
        with pytest.raises(ups.UpsError) as raised:
            ups.apply(BEFORE, patch)

        # Assert
        assert f"expects {zlib.crc32(b'AXCDF'):08X}" in str(raised.value)


class TestDamage:
    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            (b"IPS1" + bytes(12), "not a UPS patch"),
            (b"UPS1" + bytes(8), "too short"),
            (sealed(BODY)[:-1] + b"\x00", "damaged"),
            (sealed(b"UPS1\x84\x85\x81\x1a"), "no terminator"),
            (sealed(b"UPS1\x84\x85\x89\x1a\x00"), "past the end"),
            (sealed(b"UPS1\x84\x85\x01"), "ends inside a number"),
        ],
    )
    def test_a_damaged_patch_is_refused(self, patch, message):
        # Arrange
        source = BEFORE

        # Act
        with pytest.raises(ups.UpsError) as raised:
            ups.apply(source, patch)

        # Assert
        assert message in str(raised.value)


class TestXor:
    def test_xor_combines_equal_length_strings(self):
        # Arrange
        left, right = b"\x0f\xf0", b"\xff\xff"

        # Act
        combined = ups.xor(left, right)

        # Assert
        assert combined == b"\xf0\x0f"


class TestTheSizeCeiling:
    def test_a_patch_claiming_a_huge_result_is_refused_before_allocating(self):
        # Arrange
        patch = sealed(b"UPS1\x84" + varint.encode(1 << 40))

        # Act
        with pytest.raises(imagesize.ImageSizeError) as raised:
            ups.apply(BEFORE, patch)

        # Assert
        assert "ceiling" in str(raised.value)


class TestReverting:
    def test_a_patched_image_goes_back_to_its_source(self):
        # Arrange
        patch = sealed(BODY)

        # Act
        result = ups.revert(AFTER, patch)

        # Assert
        assert result == BEFORE

    def test_a_shrinking_patch_restores_the_bytes_it_cut(self):
        # Arrange
        before, after = b"ABCDEFGH", b"AB"
        patch = ups.build(before, after)

        # Act
        result = ups.revert(after, patch)

        # Assert
        assert result == before

    def test_an_image_the_patch_did_not_produce_is_refused(self):
        # Arrange
        patch = sealed(BODY)

        # Act
        with pytest.raises(ups.UpsError) as raised:
            ups.revert(BEFORE, patch)

        # Assert
        assert "made to produce a 5-byte image" in str(raised.value)
