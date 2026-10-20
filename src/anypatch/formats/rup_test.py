import hashlib

import pytest

from n64_save_patches import imagesize, rup


def md5(data: bytes) -> bytes:
    return hashlib.md5(data).digest()


def header(description: bytes = b"") -> bytes:
    fields = b"NINJA2\x00" + bytes(84 + 11 + 256 + 48 + 48 + 8 + 512)
    return fields + description.ljust(1074, b"\x00")


def opened(before: bytes, after: bytes, overflow: bytes = b"") -> bytes:
    sizes = bytes([1, len(before), 1, len(after)])
    return b"\x01\x00\x00" + sizes + md5(before) + md5(after) + overflow


GROW = opened(b"ABCD", b"AXCDEF", b"A\x01\x02\xba\xb9") + b"\x02\x01\x01\x01\x01\x1a"


class TestBuilding:
    def test_a_worked_example_gives_the_exact_bytes(self):
        # Arrange
        before, after = b"ABCD", b"AXCDEF"

        # Act
        patch = rup.build(before, after, description="hi")

        # Assert
        assert patch == header(b"hi") + GROW + b"\x00"

    def test_a_shrinking_change_round_trips(self):
        # Arrange
        before, after = b"ABCDEF", b"AXCD"
        patch = rup.build(before, after)

        # Act
        replayed = rup.apply(before, patch)

        # Assert
        assert replayed == after

    def test_a_long_change_uses_wider_numbers(self):
        # Arrange
        before = bytes(70000)
        after = before[:300] + b"\x01" * 600 + before[900:]
        patch = rup.build(before, after)

        # Act
        replayed = rup.apply(before, patch)

        # Assert
        assert replayed == after
        assert b"\x02\x02\x2c\x01\x02\x58\x02" in patch


class TestApplying:
    def test_the_worked_example_applies_to_its_source(self):
        # Arrange
        patch = header() + GROW + b"\x00"

        # Act
        replayed = rup.apply(b"ABCD", patch)

        # Assert
        assert replayed == b"AXCDEF"

    def test_a_dump_that_already_carries_the_patch_comes_back_unchanged(self):
        # Arrange
        patch = header() + GROW + b"\x00"

        # Act
        replayed = rup.apply(b"AXCDEF", patch)

        # Assert
        assert replayed == b"AXCDEF"

    def test_the_file_entry_matching_the_dump_is_the_one_applied(self):
        # Arrange
        other = opened(b"WXYZ", b"WXYQ") + b"\x02\x01\x03\x01\x01\x0b"
        patch = header() + other + GROW + b"\x00"

        # Act
        replayed = rup.apply(b"ABCD", patch)

        # Assert
        assert replayed == b"AXCDEF"

    def test_another_dump_is_refused_naming_every_expected_md5(self):
        # Arrange
        patch = header() + GROW + b"\x00"

        # Act
        with pytest.raises(rup.RupError) as raised:
            rup.apply(b"ZZZZ", patch)

        # Assert
        assert str(raised.value) == (
            f"made for MD5 {md5(b'ABCD').hex()}, but this dump is {md5(b'ZZZZ').hex()}"
        )

    def test_a_result_with_the_wrong_md5_is_refused(self):
        # Arrange
        patch = header() + opened(b"ABCD", b"ABCE") + b"\x02\x01\x01\x01\x01\x1a\x00"

        # Act
        with pytest.raises(rup.RupError) as raised:
            rup.apply(b"ABCD", patch)

        # Assert
        assert f"the patch expects {md5(b'ABCE').hex()}" in str(raised.value)


class TestDamage:
    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            (b"NINJA1" + bytes(2042), "not a RUP patch"),
            (b"NINJA2" + bytes(10), "too short"),
            (header() + b"\x07", "unknown command 0x07"),
            (header() + b"\x02\x01\x00\x01\x01\x1a\x00", "before any file"),
            (header() + opened(b"ABCD", b"ABCDE", b"Q\x01\x01\x00") + b"\x00", "overflow mode"),
            (header() + GROW, "no end command"),
            (header() + opened(b"ABCD", b"ABCD") + b"\x02\x01\x03\x01\x02ab\x00", "runs past"),
            (header() + b"\x01\x09", "number of 9 bytes"),
            (header() + b"\x01\x01", "ends inside a number"),
            (header() + b"\x01\x01\x05ab", "ends inside"),
        ],
    )
    def test_a_damaged_patch_is_refused(self, patch, message):
        # Arrange
        source = b"ABCD"

        # Act
        with pytest.raises(rup.RupError) as raised:
            rup.apply(source, patch)

        # Assert
        assert message in str(raised.value)


class TestTheSizeCeiling:
    def test_a_patch_claiming_a_huge_result_is_refused_before_allocating(self):
        # Arrange
        sizes = bytes([1, 4, 6]) + (1 << 40).to_bytes(6, "little")
        entry = b"\x01\x00\x00" + sizes + md5(b"ABCD") + md5(b"x") + b"A\x00"
        patch = header() + entry + b"\x00"

        # Act
        with pytest.raises(imagesize.ImageSizeError) as raised:
            rup.apply(b"ABCD", patch)

        # Assert
        assert "ceiling" in str(raised.value)
