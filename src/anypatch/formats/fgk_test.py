import pytest

from anypatch.formats import fgk


class TestDecoding:
    def test_the_first_symbol_is_its_index_among_unseen_symbols_most_significant_bit_first(self):
        # Arrange
        decoder = fgk.Decoder()

        # Act
        out = decoder.decode(b"\x82", 1)

        # Assert
        assert out == b"A"

    def test_a_symbol_seen_before_is_sent_as_its_path_in_the_tree(self):
        # Arrange
        decoder = fgk.Decoder()

        # Act
        out = decoder.decode(b"\x82\x01", 2)

        # Assert
        assert out == b"AA"

    def test_a_new_symbol_after_others_is_the_path_to_the_unseen_list_then_its_index(self):
        # Arrange
        decoder = fgk.Decoder()

        # Act
        out = decoder.decode(b"\x82\x09\x02", 3)

        # Assert
        assert out == b"AAB"

    def test_the_tree_carries_over_to_the_next_section(self):
        # Arrange
        decoder = fgk.Decoder()
        decoder.decode(b"\x82", 1)

        # Act
        out = decoder.decode(b"\x01", 1)

        # Assert
        assert out == b"A"


class TestRefusals:
    def test_input_that_ends_before_the_output_is_refused(self):
        # Arrange
        decoder = fgk.Decoder()

        # Act
        with pytest.raises(fgk.FgkError) as raised:
            decoder.decode(b"\x82", 2)

        # Assert
        assert "end of input" in str(raised.value)

    def test_input_left_after_the_output_is_refused(self):
        # Arrange
        decoder = fgk.Decoder()

        # Act
        with pytest.raises(fgk.FgkError) as raised:
            decoder.decode(b"\x82\x00", 1)

        # Assert
        assert "1 bytes after" in str(raised.value)

    def test_an_empty_output_is_refused(self):
        # Arrange
        decoder = fgk.Decoder()

        # Act
        with pytest.raises(fgk.FgkError) as raised:
            decoder.decode(b"", 0)

        # Assert
        assert "empty" in str(raised.value)


def bits_for(twin: fgk.Decoder, symbol: int) -> list[int]:
    if twin.weight[symbol] == 0:
        where, node = 0, twin.zeros
        while node != symbol:
            node, where = twin.right_child[node], where + 1
        width = twin.index_bits()
        index = [(where >> shift) & 1 for shift in reversed(range(width))]
        node = twin.zeros
    else:
        index, node = [], symbol
    path: list[int] = []
    while node != twin.root:
        parent = twin.parent[node]
        path, node = [1 if twin.right_child[parent] == node else 0, *path], parent
    return path + index


def encode(symbols: list[int]) -> bytes:
    twin, stream = fgk.Decoder(), []
    for symbol in symbols:
        bits = bits_for(twin, symbol)
        finished = [twin.bit(bit) for bit in bits]
        assert finished[-1] or not bits
        assert twin.symbol() == symbol
        stream += bits
    stream += [0] * (-len(stream) % 8)
    return bytes(
        sum(b << i for i, b in enumerate(stream[at : at + 8])) for at in range(0, len(stream), 8)
    )


class TestEveryBranch:
    def test_a_stream_using_every_symbol_with_repeats_decodes_exactly(self):
        # Arrange
        order = [(at * 167 + 13) % 256 for at in range(256)]
        early = [1, 1, 1, 2, 2, 1, 3, 3, 2, 2, 2, 4, 4, 4, 4, 1]
        symbols = (
            early + [s for pair in zip(order, order[::-1], strict=True) for s in pair] + order[:40]
        )
        stream = encode(symbols)

        # Act
        out = fgk.Decoder().decode(stream, len(symbols))

        # Assert
        assert out == bytes(symbols)

    def test_an_index_past_the_unseen_list_lands_on_its_last_entry(self):
        # Arrange
        decoder = fgk.Decoder()
        decoder.decode(b"\x82", 1)
        stream = bytes([0b11111110, 0b00000001])

        # Act
        out = decoder.decode(stream, 1)

        # Assert
        assert out == b"\xff"
