import bz2
import struct

import pytest

from anypatch.formats import bdf, imagesize

SIGN = 1 << 63


def offt(value: int) -> bytes:
    return struct.pack("<Q", abs(value) | (SIGN if value < 0 else 0))


def unpacked(field: bytes) -> int:
    raw = struct.unpack("<Q", field)[0]
    return -(raw & ~SIGN) if raw & SIGN else raw


def handmade(triples: list[tuple[int, int, int]], diff: bytes, extra: bytes, size: int) -> bytes:
    control = bz2.compress(b"".join(offt(x) + offt(y) + offt(z) for x, y, z in triples))
    packed = bz2.compress(diff)
    header = b"BSDIFF40" + offt(len(control)) + offt(len(packed)) + offt(size)
    return header + control + packed + bz2.compress(extra)


def sections(patch: bytes) -> tuple[bytes, bytes, bytes, int]:
    control, diff, size = (unpacked(patch[at : at + 8]) for at in (8, 16, 24))
    blocks = patch[32:], patch[32 + control :], patch[32 + control + diff :]
    parts = (
        bz2.decompress(blocks[0][:control]),
        bz2.decompress(blocks[1][:diff]),
        bz2.decompress(blocks[2]),
    )
    return parts[0], parts[1], parts[2], size


class TestBytewiseArithmetic:
    def test_subtraction_wraps_each_byte_on_its_own(self):
        # Arrange
        left, right = b"\x00\x10\x80", b"\x01\x01\x81"

        # Act
        found = bdf.subtract(left, right)

        # Assert
        assert found == b"\xff\x0f\xff"

    def test_addition_wraps_each_byte_on_its_own(self):
        # Arrange
        left, right = b"\xff\x0f\xff", b"\x01\x01\x81"

        # Act
        found = bdf.add(left, right)

        # Assert
        assert found == b"\x00\x10\x80"


class TestBuilding:
    def test_one_control_triple_carries_the_whole_change(self):
        # Arrange
        before, after = b"ABCD", b"AXCDE"

        # Act
        patch = bdf.build(before, after)

        # Assert
        control, diff, extra, size = sections(patch)
        assert patch[:8] == b"BSDIFF40"
        assert control == offt(4) + offt(1) + offt(0)
        assert diff == b"\x00\x16\x00\x00"
        assert extra == b"E"
        assert size == 5

    @pytest.mark.parametrize(
        ("before", "after"),
        [(b"ABCDEFGH", b"ABxD"), (b"AB", b"ABCDEF"), (bytes(range(256)) * 9, bytes(2304))],
    )
    def test_a_change_round_trips(self, before, after):
        # Arrange
        patch = bdf.build(before, after)

        # Act
        replayed = bdf.apply(before, patch)

        # Assert
        assert replayed == after


class TestApplying:
    def test_seeks_move_the_old_cursor_both_ways_and_out_of_range_reads_add_zero(self):
        # Arrange
        patch = handmade([(2, 1, 1), (2, 0, -6), (2, 0, 0)], b"\x00\x00\x00\x00\x05\x05", b"!", 7)

        # Act
        replayed = bdf.apply(b"ABCD", patch)

        # Assert
        assert replayed == b"AB!D\x00\x05F"

    def test_a_read_wholly_past_the_old_file_adds_zero(self):
        # Arrange
        patch = handmade([(0, 0, 10), (1, 0, 0)], b"\x07", b"", 1)

        # Act
        replayed = bdf.apply(b"ABCD", patch)

        # Assert
        assert replayed == b"\x07"


class TestDamage:
    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            (b"BSDIFF41" + bytes(24), "not a BDF patch"),
            (b"BSDIFF40" + bytes(8), "too short"),
            (b"BSDIFF40" + offt(-1) + offt(0) + offt(0), "negative"),
            (b"BSDIFF40" + offt(99) + offt(0) + offt(0), "ends inside"),
            (b"BSDIFF40" + offt(4) + offt(0) + offt(0) + b"junk", "bzip2"),
            (handmade([], b"", b"", 0)[:32] + b"x", "ends inside"),
        ],
    )
    def test_a_damaged_header_is_refused(self, patch, message):
        # Arrange
        source = b"ABCD"

        # Act
        with pytest.raises(bdf.BdfError) as raised:
            bdf.apply(source, patch)

        # Assert
        assert message in str(raised.value)

    @pytest.mark.parametrize(
        ("triples", "diff", "extra", "size", "message"),
        [
            ([(4, 0, 0)], b"\x00" * 4, b"", 3, "past the 3-byte target"),
            ([(-1, 0, 0)], b"", b"", 0, "negative"),
            ([(4, 0, 0)], b"\x00" * 3, b"", 4, "diff block"),
            ([(0, 2, 0)], b"", b"x", 2, "extra block"),
            ([(2, 0, 0)], b"\x00" * 2, b"", 4, "write 2 of 4 bytes"),
        ],
    )
    def test_a_damaged_control_list_is_refused(self, triples, diff, extra, size, message):
        # Arrange
        patch = handmade(triples, diff, extra, size)

        # Act
        with pytest.raises(bdf.BdfError) as raised:
            bdf.apply(b"ABCD", patch)

        # Assert
        assert message in str(raised.value)

    def test_a_control_block_of_the_wrong_length_is_refused(self):
        # Arrange
        control = bz2.compress(bytes(23))
        packed = bz2.compress(b"")
        header = b"BSDIFF40" + offt(len(control)) + offt(len(packed)) + offt(0)
        patch = header + control + packed + bz2.compress(b"")

        # Act
        with pytest.raises(bdf.BdfError) as raised:
            bdf.apply(b"ABCD", patch)

        # Assert
        assert "multiple of 24" in str(raised.value)


class TestTheSizeCeiling:
    def test_a_patch_claiming_a_huge_result_is_refused_before_allocating(self):
        # Arrange
        patch = handmade([], b"", b"", 1 << 40)

        # Act
        with pytest.raises(imagesize.ImageSizeError) as raised:
            bdf.apply(b"ABCD", patch)

        # Assert
        assert "ceiling" in str(raised.value)
