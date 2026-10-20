import struct

import pytest

from anypatch.formats import apswrite

KNUTH = 2654435761


def rom(size: int = 0x100, cart: bytes = b"NS", country: int = ord("E")) -> bytes:
    image = bytearray(size)
    image[0:4] = b"\x80\x37\x12\x40"
    struct.pack_into(">II", image, apswrite.ROM_CRC_OFFSET, 0xCA12B547, 0x71FA4EE4)
    image[apswrite.ROM_CART_OFFSET : apswrite.ROM_CART_OFFSET + 2] = cart
    image[apswrite.ROM_COUNTRY_OFFSET] = country
    for at in range(0x40, size, 4):
        struct.pack_into(">I", image, at, (at * KNUTH) & 0xFFFFFFFF)
    return bytes(image)


def changed(image: bytes, at: int, word: int) -> bytes:
    out = bytearray(image)
    struct.pack_into(">I", out, at, word)
    return bytes(out)


class TestTheHeaderThatBindsAPatchToItsDump:
    def test_the_magic_and_type_identify_it_as_an_n64_patch(self):
        # Arrange
        before = rom()

        # Act
        patch = apswrite.build(before, changed(before, 0x80, 0))

        # Assert
        assert patch[: len(apswrite.MAGIC)] == apswrite.MAGIC
        assert patch[len(apswrite.MAGIC)] == apswrite.TYPE_N64

    def test_the_checksum_pair_is_copied_from_the_dump_being_patched(self):
        # Arrange
        before = rom()

        # Act
        patch = apswrite.build(before, changed(before, 0x80, 0))

        # Assert
        carried = struct.unpack_from(">II", patch, apswrite.CRC_OFFSET)
        assert carried == (0xCA12B547, 0x71FA4EE4)

    def test_the_cart_code_and_country_are_copied_from_the_dump(self):
        # Arrange
        before = rom(cart=b"ZS", country=ord("J"))

        # Act
        patch = apswrite.build(before, changed(before, 0x80, 0))

        # Assert
        assert patch[apswrite.CART_OFFSET : apswrite.CART_OFFSET + 2] == b"ZS"
        assert patch[apswrite.COUNTRY_OFFSET] == ord("J")

    def test_the_declared_size_is_the_length_of_the_dump(self):
        # Arrange
        before = rom(size=0x200)

        # Act
        patch = apswrite.build(before, changed(before, 0x80, 0))

        # Assert
        assert struct.unpack_from("<I", patch, apswrite.SIZE_OFFSET)[0] == 0x200

    def test_native_byte_order_is_declared_because_the_documented_value_is_inverted(self):
        # Arrange
        before = rom()

        # Act
        patch = apswrite.build(before, changed(before, 0x80, 0))

        # Assert
        assert patch[apswrite.FORMAT_OFFSET] == 1
        assert apswrite.FORMAT_BYTESWAPPED == 0

    def test_a_description_is_carried_and_truncated_to_the_field(self):
        # Arrange
        before = rom()
        overlong = "x" * (apswrite.DESCRIPTION_LENGTH + 20)

        # Act
        patch = apswrite.build(before, changed(before, 0x80, 0), description=overlong)

        # Assert
        start = apswrite.DESCRIPTION_OFFSET
        assert patch[start : start + apswrite.DESCRIPTION_LENGTH] == b"x" * 50


class TestWhatThePatchReplays:
    def test_applying_a_built_patch_reproduces_the_target_exactly(self):
        # Arrange
        before = rom()
        after = changed(changed(before, 0x80, 0), 0xC0, 0xDEADBEEF)

        # Act
        replayed = apswrite.apply(before, apswrite.build(before, after))

        # Assert
        assert replayed == after

    def test_a_long_identical_run_is_stored_as_a_run_rather_than_bytes(self):
        # Arrange
        before = rom()
        after = bytearray(before)
        after[0x80:0xC0] = b"\x00" * 0x40

        # Act
        patch = apswrite.build(before, bytes(after))

        # Assert
        assert apswrite.apply(before, patch) == bytes(after)
        assert len(patch) < apswrite.RECORDS_OFFSET + 0x40

    def test_a_run_record_stores_the_value_before_the_count(self):
        # Arrange
        before = rom()
        after = bytearray(before)
        after[0x80:0xC0] = b"\xa5" * 0x40

        # Act
        patch = apswrite.build(before, bytes(after))

        # Assert
        assert patch[apswrite.RECORDS_OFFSET :] == struct.pack("<IBBB", 0x80, 0, 0xA5, 0x40)

    def test_a_community_run_record_writes_its_value_count_times(self):
        # Arrange
        before = rom()
        patch = apswrite.build(before, before) + struct.pack("<IB", 0x80, 0) + b"\x20\x04"

        # Act
        replayed = apswrite.apply(before, patch)

        # Assert
        assert replayed == before[:0x80] + b"    " + before[0x84:]

    def test_a_run_longer_than_one_record_is_split_and_still_replays(self):
        # Arrange
        before = rom(size=0x600)
        after = bytearray(before)
        after[0x100:0x500] = b"\xa5" * 0x400

        # Act
        replayed = apswrite.apply(before, apswrite.build(before, bytes(after)))

        # Assert
        assert replayed == bytes(after)

    def test_a_literal_chunk_longer_than_one_record_is_split_and_still_replays(self):
        # Arrange
        before = bytes(0x400)
        after = rom(size=0x400)

        # Act
        replayed = apswrite.apply(before, apswrite.build(before, after))

        # Assert
        assert replayed == after

    def test_scattered_differences_each_become_their_own_record(self):
        # Arrange
        before = rom()
        after = changed(changed(before, 0x50, 1), 0xE0, 2)

        # Act
        replayed = apswrite.apply(before, apswrite.build(before, after))

        # Assert
        assert replayed == after

    def test_two_identical_images_produce_a_patch_with_no_records(self):
        # Arrange
        before = rom()

        # Act
        patch = apswrite.build(before, before)

        # Assert
        assert len(patch) == apswrite.RECORDS_OFFSET


class TestWhatItRefuses:
    def test_an_image_too_short_to_hold_a_header_is_refused(self):
        # Arrange
        stub = bytes(apswrite.HEADER_MINIMUM - 1)

        # Act
        with pytest.raises(ValueError) as raised:
            apswrite.build(stub, stub)

        # Assert
        assert "too short" in str(raised.value)


def header_byte(patch: bytes, at: int, value: int) -> bytes:
    out = bytearray(patch)
    out[at] = value
    return bytes(out)


class TestSizeChanges:
    def test_a_longer_target_declares_its_size_and_writes_the_tail(self):
        # Arrange
        before = rom()
        after = before + bytes(range(1, 0x21))

        # Act
        patch = apswrite.build(before, after)

        # Assert
        assert struct.unpack_from("<I", patch, apswrite.SIZE_OFFSET)[0] == len(after)
        assert apswrite.apply(before, patch) == after

    def test_a_shorter_target_is_cut_to_the_declared_size(self):
        # Arrange
        before = rom(0x200)
        after = before[:0x180]

        # Act
        patch = apswrite.build(before, after)

        # Assert
        assert apswrite.apply(before, patch) == after


class TestWhatApplyRefuses:
    def test_a_patch_bound_to_another_dump_names_both(self):
        # Arrange
        before = rom()
        patch = apswrite.build(before, changed(before, 0x80, 1))
        other = changed(before, apswrite.ROM_CRC_OFFSET, 0x12345678)

        # Act
        with pytest.raises(apswrite.ApsError) as raised:
            apswrite.apply(other, patch)

        # Assert
        assert (
            str(raised.value)
            == "bound to NSE CA12B547 71FA4EE4, but this dump is NSE 12345678 71FA4EE4"
        )

    def test_a_dump_too_short_for_a_header_is_refused(self):
        # Arrange
        before = rom()
        patch = apswrite.build(before, before)

        # Act
        with pytest.raises(apswrite.ApsError) as raised:
            apswrite.apply(bytes(8), patch)

        # Assert
        assert "this dump is no header" in str(raised.value)

    @pytest.mark.parametrize(
        ("at", "value", "message"),
        [
            (0, ord("X"), "not an APS patch"),
            (len(apswrite.MAGIC), 0, "another system"),
            (len(apswrite.MAGIC) + 1, 1, "another system"),
            (apswrite.FORMAT_OFFSET, apswrite.FORMAT_BYTESWAPPED, "byte-swapped"),
        ],
    )
    def test_a_header_it_cannot_read_is_refused(self, at, value, message):
        # Arrange
        before = rom()
        patch = header_byte(apswrite.build(before, before), at, value)

        # Act
        with pytest.raises(apswrite.ApsError) as raised:
            apswrite.apply(before, patch)

        # Assert
        assert message in str(raised.value)

    @pytest.mark.parametrize(
        ("tail", "message"),
        [
            (b"\x80\x00", "ends inside the record"),
            (struct.pack("<IB", 0x80, 4) + b"ab", "ends inside the 4-byte record"),
            (struct.pack("<IB", 0x80, 0) + b"\x05", "ends inside the run record"),
            (struct.pack("<IB", 0xFE, 4) + b"abcd", "past the declared size"),
        ],
    )
    def test_a_damaged_record_is_refused(self, tail, message):
        # Arrange
        before = rom()
        patch = apswrite.build(before, before) + tail

        # Act
        with pytest.raises(apswrite.ApsError) as raised:
            apswrite.apply(before, patch)

        # Assert
        assert message in str(raised.value)
