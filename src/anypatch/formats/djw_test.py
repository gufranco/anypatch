import pytest

from n64_save_patches import djw, vcdiff
from n64_save_patches import xdelta_vectors_test_support as vectors


def bits_lsb_first(fields: list[tuple[int, int]]) -> bytes:
    stream = [
        bit for value, width in fields for bit in ((value >> s) & 1 for s in reversed(range(width)))
    ]
    stream += [0] * (-len(stream) % 8)
    return bytes(
        sum(bit << index for index, bit in enumerate(stream[at : at + 8]))
        for at in range(0, len(stream), 8)
    )


class TestTheBitReader:
    def test_fields_are_read_lowest_bit_of_each_byte_first_and_most_significant_first(self):
        # Arrange
        reader = djw.Bits(bits_lsb_first([(0b101, 3), (0b0110, 4), (0b1, 1), (0b11, 2)]))

        # Act
        values = [reader.read(3), reader.read(4), reader.read(1), reader.read(2)]

        # Assert
        assert values == [0b101, 0b0110, 0b1, 0b11]

    def test_reading_past_the_end_is_refused(self):
        # Arrange
        reader = djw.Bits(b"\xff")

        # Act
        with pytest.raises(djw.DjwError) as raised:
            reader.read(9)

        # Assert
        assert "end of input" in str(raised.value)


class TestCanonicalCodes:
    def test_shorter_codes_come_first_and_ties_go_to_the_lower_symbol(self):
        # Arrange
        lengths = [2, 1, 3, 3]
        reader = djw.Bits(bits_lsb_first([(0b0, 1), (0b10, 2), (0b110, 3), (0b111, 3)]))
        table = djw.Table.build(lengths, 3)

        # Act
        symbols = [table.symbol(reader) for _ in range(4)]

        # Assert
        assert symbols == [1, 0, 2, 3]

    def test_a_code_no_table_entry_matches_is_refused(self):
        # Arrange
        table = djw.Table.build([1, 0, 0, 0], 3)
        reader = djw.Bits(bits_lsb_first([(0b1, 1), (0b11, 2)]))

        # Act
        with pytest.raises(djw.DjwError) as raised:
            table.symbol(reader)

        # Assert
        assert "invalid code" in str(raised.value)

    def test_a_table_with_no_codes_refuses_every_symbol(self):
        # Arrange
        table = djw.Table.build([0, 0, 0], 3)

        # Act
        with pytest.raises(djw.DjwError) as raised:
            table.symbol(djw.Bits(b"\x00"))

        # Assert
        assert "invalid code" in str(raised.value)


class TestDecode:
    def test_an_empty_output_is_refused(self):
        # Arrange
        data = b"\x00"

        # Act
        with pytest.raises(djw.DjwError) as raised:
            djw.decode(data, 0)

        # Assert
        assert "empty" in str(raised.value)


def first_data_section(patch: bytes) -> tuple[int, bytes]:
    at = len(vcdiff.MAGIC) + 2
    flags, at = patch[len(vcdiff.MAGIC) + 1], at + 1
    length, at = read_varint(patch, at) if flags & vcdiff.VCD_APPHEADER else (0, at)
    at += length + 1
    for _ in range(4):
        _, at = read_varint(patch, at)
    at += 1
    data_length, at = read_varint(patch, at)
    for _ in range(2):
        _, at = read_varint(patch, at)
    raw = patch[at + 4 : at + 4 + data_length]
    size, start = read_varint(raw, 0)
    return size, raw[start:]


def read_varint(data: bytes, at: int) -> tuple[int, int]:
    value = 0
    while data[at] & 0x80:
        value, at = value << 7 | data[at] & 0x7F, at + 1
    return value << 7 | data[at], at + 1


def flipped(payload: bytes, at: int, mask: int) -> bytes:
    return payload[:at] + bytes([payload[at] ^ mask]) + payload[at + 1 :]


class TestRealSections:
    def test_a_section_from_xdelta3_with_five_groups_decodes(self):
        # Arrange
        size, payload = first_data_section(vectors.PATCHES["djw-groups"])

        # Act
        out = djw.decode(payload, size)

        # Assert
        assert len(out) == size
        assert djw.Bits(payload).read(3) + 1 == 5

    @pytest.mark.parametrize(
        ("at", "mask", "message"),
        [
            (0, 0x04, "invalid code"),
            (0, 0x01, "repeats past"),
            (0, 0x10, "bytes after"),
            (14, 0x08, "end of input"),
        ],
    )
    def test_a_damaged_section_is_refused_with_its_reason(self, at, mask, message):
        # Arrange
        size, payload = first_data_section(vectors.PATCHES["djw-groups"])

        # Act
        with pytest.raises(djw.DjwError) as raised:
            djw.decode(flipped(payload, at, mask), size)

        # Assert
        assert message in str(raised.value)
