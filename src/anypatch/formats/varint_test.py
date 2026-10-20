import pytest

from n64_save_patches import varint


class TestTheByuuNumbers:
    @pytest.mark.parametrize(
        ("value", "encoded"),
        [
            (0, b"\x80"),
            (127, b"\xff"),
            (128, b"\x00\x80"),
            (255, b"\x7f\x80"),
            (16511, b"\x7f\xff"),
            (16512, b"\x00\x00\x80"),
        ],
    )
    def test_each_value_has_one_encoding_and_reads_back(self, value, encoded):
        # Arrange
        number = value

        # Act
        written = varint.encode(number)

        # Assert
        assert written == encoded
        assert varint.decode(encoded, 0) == (value, len(encoded))

    def test_a_number_cut_short_is_refused(self):
        # Arrange
        data = b"\x00\x00"

        # Act
        with pytest.raises(varint.VarintError) as raised:
            varint.decode(data, 0)

        # Assert
        assert "ends inside a number" in str(raised.value)

    def test_a_number_longer_than_ten_bytes_is_refused(self):
        # Arrange
        data = bytes(11) + b"\x80"

        # Act
        with pytest.raises(varint.VarintError) as raised:
            varint.decode(data, 0)

        # Assert
        assert "too long" in str(raised.value)

    def test_a_value_needing_more_than_ten_bytes_is_refused(self):
        # Arrange
        value = 1 << 80

        # Act
        with pytest.raises(varint.VarintError) as raised:
            varint.encode(value)

        # Assert
        assert "too large" in str(raised.value)
