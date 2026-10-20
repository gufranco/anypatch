import functools
import struct
import zlib

import pytest

from anypatch.formats import imagesize, pmsr

BASE_SIZE = 41943040
BASE_CRC = 0xA7F5CD7E
CRC_BITS = 32


def reduced(value: int, mask: int, basis: list[tuple[int, int]]) -> tuple[int, int]:
    for vector, vector_mask in sorted(basis, reverse=True):
        if value ^ vector < value:
            value, mask = value ^ vector, mask ^ vector_mask
    return value, mask


def solved(columns: list[int], goal: int) -> int:
    basis: list[tuple[int, int]] = []
    for bit, column in enumerate(columns):
        value, mask = reduced(column, 1 << bit, basis)
        basis = [*basis, (value, mask)] if value else basis
    return reduced(goal, 0, basis)[1]


@functools.cache
def paper_mario() -> bytes:
    body = bytes(BASE_SIZE - 4)
    running = zlib.crc32(body)
    empty = zlib.crc32(bytes(4), running)
    columns = [
        zlib.crc32((1 << bit).to_bytes(4, "little"), running) ^ empty for bit in range(CRC_BITS)
    ]
    tail = solved(columns, BASE_CRC ^ empty).to_bytes(4, "little")
    return body + tail


def star_rod(records: list[tuple[int, bytes]]) -> bytes:
    body = b"".join(struct.pack(">II", at, len(data)) + data for at, data in records)
    return b"PMSR" + struct.pack(">I", len(records)) + body


def literal_yay0(data: bytes) -> bytes:
    words = -(-len(data) // 32)
    flags = b"\xff" * (4 * words)
    link = 0x10 + len(flags)
    return b"Yay0" + struct.pack(">III", len(data), link, link) + flags + data


def edited(data: bytes, at: int, new: bytes) -> bytes:
    return data[:at] + new + data[at + len(new) :]


RECORDS = [(0x1000, b"star"), (0x20, b"rod!")]


class TestTheBase:
    def test_the_forged_base_is_paper_mario_usa_one_point_zero(self):
        # Arrange
        base = paper_mario()

        # Act
        found = (len(base), zlib.crc32(base))

        # Assert
        assert found == (BASE_SIZE, BASE_CRC)


class TestYay0:
    @pytest.mark.parametrize(
        ("stream", "expected"),
        [
            (
                b"Yay0" + struct.pack(">III", 10, 0x14, 0x16) + b"\xc0\x00\x00\x00\x60\x01AB",
                b"AB" * 5,
            ),
            (
                b"Yay0" + struct.pack(">III", 19, 0x14, 0x16) + b"\x80\x00\x00\x00\x00\x00Z\x00",
                b"Z" * 19,
            ),
        ],
    )
    def test_short_and_long_copies_decode(self, stream, expected):
        # Arrange
        data = stream

        # Act
        decoded = pmsr.yay0(data)

        # Assert
        assert decoded == expected

    @pytest.mark.parametrize(
        ("stream", "message"),
        [
            (b"Yay0" + struct.pack(">III", 4, 0x14, 0x16) + b"\x00\x00\x00\x00\x10\x05", "before"),
            (b"Yay0" + struct.pack(">III", 4, 0x14, 0x14) + b"\xff\x00\x00\x00AB", "ends"),
            (b"Yay0" + bytes(4), "header"),
        ],
    )
    def test_a_damaged_stream_is_refused(self, stream, message):
        # Arrange
        data = stream

        # Act
        with pytest.raises(pmsr.PmsrError) as raised:
            pmsr.yay0(data)

        # Assert
        assert message in str(raised.value)


class TestApplying:
    def test_records_overwrite_paper_mario(self):
        # Arrange
        base = paper_mario()

        # Act
        replayed = pmsr.apply(base, star_rod(RECORDS))

        # Assert
        assert replayed == edited(edited(base, 0x1000, b"star"), 0x20, b"rod!")

    def test_a_yay0_wrapped_patch_applies_the_same(self):
        # Arrange
        base = paper_mario()

        # Act
        replayed = pmsr.apply(base, literal_yay0(star_rod(RECORDS)))

        # Assert
        assert replayed == edited(edited(base, 0x1000, b"star"), 0x20, b"rod!")

    def test_a_record_past_the_end_extends_the_image(self):
        # Arrange
        base = paper_mario()

        # Act
        replayed = pmsr.apply(base, star_rod([(BASE_SIZE + 2, b"xy")]))

        # Assert
        assert replayed == base + b"\x00\x00xy"

    def test_a_dump_that_already_carries_the_patch_comes_back_unchanged(self):
        # Arrange
        carried = b"rod!".rjust(0x24, b"\x00") + b"star".rjust(0x1000 - 0x24 + 4, b"\x00")

        # Act
        replayed = pmsr.apply(carried, star_rod(RECORDS))

        # Assert
        assert replayed == carried

    def test_another_dump_is_refused_naming_paper_mario(self):
        # Arrange
        source = bytes(64)

        # Act
        with pytest.raises(pmsr.PmsrError) as raised:
            pmsr.apply(source, star_rod(RECORDS))

        # Assert
        assert str(raised.value) == (
            "made for Paper Mario USA 1.0, 41,943,040 bytes with CRC32 A7F5CD7E; "
            f"this dump is 64 bytes with CRC32 {zlib.crc32(source):08X}"
        )


class TestDamage:
    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            (b"IPS!" + bytes(4), "not a Star Rod patch"),
            (b"PMSR\x00\x00", "ends inside"),
            (b"PMSR" + struct.pack(">I", 2) + struct.pack(">II", 0, 1) + b"x", "ends inside"),
            (b"PMSR" + struct.pack(">I", 1) + struct.pack(">II", 0, 4) + b"x", "ends inside"),
            (literal_yay0(b"IPS!"), "not a Star Rod patch"),
        ],
    )
    def test_a_damaged_patch_is_refused(self, patch, message):
        # Arrange
        source = bytes(64)

        # Act
        with pytest.raises(pmsr.PmsrError) as raised:
            pmsr.apply(source, patch)

        # Assert
        assert message in str(raised.value)


class TestTheSizeCeiling:
    def test_a_patch_claiming_a_huge_result_is_refused_before_allocating(self):
        # Arrange
        patch = star_rod([(0x50000000, b"x")])

        # Act
        with pytest.raises(imagesize.ImageSizeError) as raised:
            pmsr.apply(paper_mario(), patch)

        # Assert
        assert "ceiling" in str(raised.value)

    def test_a_yay0_header_claiming_a_huge_result_is_refused(self):
        # Arrange
        stream = b"Yay0" + struct.pack(">III", 0x50000000, 0x14, 0x14) + bytes(4)

        # Act
        with pytest.raises(imagesize.ImageSizeError) as raised:
            pmsr.yay0(stream)

        # Assert
        assert "ceiling" in str(raised.value)
