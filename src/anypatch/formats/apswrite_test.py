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


def generic_patch(size: int, records: bytes, text: bytes = b"") -> bytes:
    description = text.ljust(apswrite.DESCRIPTION_LENGTH)
    head = apswrite.MAGIC + bytes([apswrite.TYPE_GENERIC, apswrite.ENCODING_SIMPLE])
    return head + description + struct.pack("<I", size) + records


class TestPatchesForFilesThatAreNotN64Roms:
    def test_a_source_without_the_n64_magic_gets_the_header_with_no_binding(self):
        # Arrange
        before = bytes(range(256)) * 4

        # Act
        patch = apswrite.build(before, before)

        # Assert
        assert patch == generic_patch(len(before), b"")

    def test_an_empty_source_can_be_grown(self):
        # Arrange
        before = b""

        # Act
        patch = apswrite.build(before, b"grown")

        # Assert
        assert patch == generic_patch(5, struct.pack("<IB", 0, 5) + b"grown")
        assert apswrite.apply(before, patch) == b"grown"

    def test_a_patch_with_no_header_written_by_another_tool_applies_to_any_source(self):
        # Arrange
        patch = generic_patch(
            6, struct.pack("<IB", 1, 2) + b"XY" + struct.pack("<IBBB", 4, 0, 0x5A, 2), b"elsewhere"
        )

        # Act
        result = apswrite.apply(b"abcdef", patch)

        # Assert
        assert result == b"aXYdZZ"

    def test_an_n64_rom_can_still_be_written_without_a_binding_when_asked(self):
        # Arrange
        before = rom()

        # Act
        patch = apswrite.build(before, before, bound=False)

        # Assert
        assert patch == generic_patch(len(before), b"")


class TestATruncatedN64Header:
    def test_it_is_refused_before_any_field_is_read(self):
        # Arrange
        before = rom()
        patch = apswrite.build(before, before)[: apswrite.RECORDS_OFFSET - 1]

        # Act
        with pytest.raises(apswrite.ApsError) as raised:
            apswrite.apply(before, patch)

        # Assert
        assert str(raised.value) == "not an APS patch: it ends inside its N64 header"


class TestReadableShapes:
    def test_a_built_patch_is_well_formed(self):
        # Arrange
        before = rom()

        # Act
        shaped = apswrite.wellformed(apswrite.build(before, changed(before, 0x80, 7)))

        # Assert
        assert shaped is True

    @pytest.mark.parametrize(
        "patch",
        [
            b"APS1",
            generic_patch(4, b"")[:-1],
            generic_patch(4, b"\x00\x00"),
            generic_patch(4, struct.pack("<IB", 0, 9) + b"ab"),
            generic_patch(4, struct.pack("<IB", 0, 0) + b"\x01"),
            apswrite.MAGIC + bytes([2, 0]) + bytes(80),
            apswrite.MAGIC + bytes([0, 1]) + bytes(80),
        ],
        ids=[
            "no-header",
            "short-size",
            "short-record",
            "short-literal",
            "short-run",
            "type-2",
            "encoding-1",
        ],
    )
    def test_a_header_or_record_that_does_not_fit_is_not(self, patch):
        # Arrange
        data = patch

        # Act
        shaped = apswrite.wellformed(data)

        # Assert
        assert shaped is False


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
            (len(apswrite.MAGIC), 2, "header type 2; only 0, no header, and 1, N64, are read"),
            (len(apswrite.MAGIC) + 1, 1, "encoding 1; only 0, simple, is read"),
            (apswrite.FORMAT_OFFSET, 7, "order byte 7"),
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


def swapped_patch(before: bytes, after: bytes) -> bytes:
    swapped = (apswrite.byteswapped(before), apswrite.byteswapped(after))
    patch = bytearray(apswrite.build(*swapped, bound=True))
    patch[apswrite.FORMAT_OFFSET] = apswrite.FORMAT_BYTESWAPPED
    patch[apswrite.CART_OFFSET : apswrite.CART_OFFSET + 2] = before[
        apswrite.ROM_CART_OFFSET : apswrite.ROM_CART_OFFSET + 2
    ]
    patch[apswrite.COUNTRY_OFFSET] = before[apswrite.ROM_COUNTRY_OFFSET]
    patch[apswrite.CRC_OFFSET : apswrite.CRC_OFFSET + 8] = before[
        apswrite.ROM_CRC_OFFSET : apswrite.ROM_CRC_OFFSET + 8
    ]
    return bytes(patch)


class TestByteSwappedPatches:
    def test_swapping_exchanges_each_pair_of_bytes(self):
        # Arrange
        data = b"\x80\x37\x12\x40"

        # Act
        swapped = apswrite.byteswapped(data)

        # Assert
        assert swapped == b"\x37\x80\x40\x12"

    def test_records_for_the_v64_image_apply_to_the_native_dump(self):
        # Arrange
        before = rom(0x200)
        after = changed(changed(before, 0x80, 0x11223344), 0x101, 0x55667788)
        patch = swapped_patch(before, after)

        # Act
        replayed = apswrite.apply(before, patch)

        # Assert
        assert replayed == after

    def test_a_byte_swapped_patch_still_checks_the_native_binding(self):
        # Arrange
        before = rom(0x200)
        patch = swapped_patch(before, changed(before, 0x80, 1))
        other = changed(before, apswrite.ROM_CRC_OFFSET, 0x12345678)

        # Act
        with pytest.raises(apswrite.ApsError) as raised:
            apswrite.apply(other, patch)

        # Assert
        assert "but this dump is NSE 12345678 71FA4EE4" in str(raised.value)

    def test_an_odd_sized_dump_cannot_be_byte_swapped(self):
        # Arrange
        data = b"\x80\x37\x12"

        # Act
        with pytest.raises(apswrite.ApsError) as raised:
            apswrite.byteswapped(data)

        # Assert
        assert str(raised.value) == "a byte-swapped patch needs an even-sized dump, not 3 bytes"
