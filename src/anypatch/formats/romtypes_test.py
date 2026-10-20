import struct

import pytest

from anypatch.formats import romtypes

KIB = 1024
BANK = 32 * KIB


def body(size: int, seed: int = 1) -> bytes:
    return bytes((at * 2654435761 + seed) >> 13 & 0xFF for at in range(size))


def lorom(size: int) -> bytes:
    image = bytearray(body(size))
    image[0x7FD5] = 0x20
    struct.pack_into("<HH", image, 0x7FDC, 0x1234, 0xFFFF - 0x1234)
    return bytes(image)


def hirom(size: int) -> bytes:
    image = bytearray(body(size, 7))
    image[0x7FD5] = 0x21
    struct.pack_into("<HH", image, 0x7FDC, 0x1111, 0xFFFF - 0x1111)
    image[0xFFD5] = 0x21
    struct.pack_into("<HH", image, 0xFFDC, 0x2222, 0xFFFF - 0x2222)
    return bytes(image)


def interleaved_halves(image: bytes) -> bytes:
    banks = [image[at : at + BANK] for at in range(0, len(image), BANK)]
    odd, even = banks[1::2], banks[0::2]
    return b"".join(odd + even)


def smd(image: bytes) -> bytes:
    header = bytearray(0x200)
    header[8:10] = b"\xaa\xbb"
    blocks = []
    for at in range(0, len(image), 16 * KIB):
        chunk = image[at : at + 16 * KIB]
        blocks.append(chunk[0::2] + chunk[1::2])
    return bytes(header) + b"".join(blocks)


def unif(prg: bytes, chr_: bytes) -> bytes:
    def chunk(name: bytes, data: bytes) -> bytes:
        return name + struct.pack("<I", len(data)) + data

    head = b"UNIF" + bytes(28)
    return head + chunk(b"MAPR", b"NROM\x00") + chunk(b"PRG0", prg) + chunk(b"CHR0", chr_)


class TestRawAndUnknownTypes:
    @pytest.mark.parametrize("kind", [romtypes.RAW, 2, 10, 255])
    def test_the_image_is_used_as_it_is(self, kind):
        # Arrange
        image = body(100)

        # Act
        found = romtypes.normalized(kind, image)

        # Assert
        assert (found.data, found.restore(b"result")) == (image, b"result")


class TestNes:
    def test_an_ines_header_is_removed_and_restored(self):
        # Arrange
        header = b"NES\x1a" + bytes(range(12))

        # Act
        found = romtypes.normalized(romtypes.NES, header + body(64))

        # Assert
        assert found.data == body(64)
        assert found.restore(b"patched") == header + b"patched"

    def test_a_famtasia_header_is_removed_and_restored(self):
        # Arrange
        header = bytearray(0x200)
        header[8:10] = b"\xaa\xbb"

        # Act
        found = romtypes.normalized(romtypes.NES, bytes(header) + body(64))

        # Assert
        assert found.data == body(64)
        assert found.restore(b"x") == bytes(header) + b"x"

    def test_unif_banks_are_joined_and_written_back_in_place(self):
        # Arrange
        image = unif(b"P" * 16, b"C" * 8)

        # Act
        found = romtypes.normalized(romtypes.NES, image)

        # Assert
        assert found.data == b"P" * 16 + b"C" * 8
        assert found.restore(b"p" * 16 + b"c" * 8) == unif(b"p" * 16, b"c" * 8)

    def test_a_dump_with_no_header_cannot_be_normalized(self):
        # Arrange
        image = body(64)

        # Act
        with pytest.raises(romtypes.RomTypeError) as raised:
            romtypes.normalized(romtypes.NES, image)

        # Assert
        assert "an iNES, Famtasia or UNIF dump" in str(raised.value)

    def test_a_unif_chunk_that_runs_past_the_end_is_refused(self):
        # Arrange
        image = b"UNIF" + bytes(28) + b"PRG0" + struct.pack("<I", 99) + b"short"

        # Act
        with pytest.raises(romtypes.RomTypeError) as raised:
            romtypes.normalized(romtypes.NES, image)

        # Assert
        assert "the UNIF chunk PRG0 at 0x20 runs past the end" in str(raised.value)


class TestSnes:
    def test_a_lorom_with_a_copier_header_loses_the_header(self):
        # Arrange
        image = lorom(4 * BANK)

        # Act
        found = romtypes.normalized(romtypes.SNES, bytes(0x200) + image)

        # Assert
        assert (found.data, found.restore(b"r")) == (image, b"r")

    def test_an_nsrt_header_is_kept_and_restored(self):
        # Arrange
        header = bytearray(0x200)
        header[0x1E8:0x1EC] = b"NSRT"

        # Act
        found = romtypes.normalized(romtypes.SNES, bytes(header) + lorom(4 * BANK))

        # Assert
        assert found.restore(b"r") == bytes(header) + b"r"

    def test_an_interleaved_hirom_is_put_back_in_bank_order(self):
        # Arrange
        image = hirom(8 * BANK)
        swapped = interleaved_halves(image)
        bank_zero_id = bytearray(swapped)
        bank_zero_id[0x7FD5] = 0x21
        struct.pack_into("<HH", bank_zero_id, 0x7FDC, 0x3333, 0xFFFF - 0x3333)

        # Act
        found = romtypes.normalized(romtypes.SNES, bytes(bank_zero_id))

        # Assert
        assert found.data == interleaved_halves_inverse(bytes(bank_zero_id))

    def test_a_20_mbit_game_doctor_interleave_follows_its_chart(self):
        # Arrange
        banks = [bytes([at]) * BANK for at in range(0x50)]
        stored = [banks[romtypes.CHART_20MBIT[at]] for at in range(0x50)]
        image = bytearray(b"".join(stored))
        image[0x7FD5] = 0x21
        struct.pack_into("<HH", image, 0x7FDC, 0x10, 0xFFEF)

        # Act
        found = romtypes.normalized(romtypes.SNES, bytes(image))

        # Assert
        assert [found.data[at * BANK + 0x8000 - 1] for at in range(0x50)][1:] == list(
            range(1, 0x50)
        )

    def test_a_super_ufo_dump_of_20_mbit_uses_the_halves_order(self):
        # Arrange
        image = bytearray(hirom(0x50 * BANK))
        image[8:16] = b"SUPERUFO"
        image[0x7FD5] = 0x21
        struct.pack_into("<HH", image, 0x7FDC, 0x10, 0xFFEF)

        # Act
        found = romtypes.normalized(romtypes.SNES, bytes(image))

        # Assert
        assert found.data == interleaved_halves_inverse(bytes(image))

    def test_a_plain_hirom_is_used_as_it_is(self):
        # Arrange
        image = bytearray(hirom(4 * BANK))
        struct.pack_into("<HH", image, 0x7FDC, 0, 0)

        # Act
        found = romtypes.normalized(romtypes.SNES, bytes(image))

        # Assert
        assert found.data == bytes(image)

    def test_a_hirom_whose_checksum_fails_is_still_used_as_it_is(self):
        # Arrange
        image = bytearray(hirom(4 * BANK))
        struct.pack_into("<HH", image, 0x7FDC, 0, 0)
        struct.pack_into("<HH", image, 0xFFDC, 0, 0)

        # Act
        found = romtypes.normalized(romtypes.SNES, bytes(image))

        # Assert
        assert found.data == bytes(image)

    def test_an_image_too_short_for_a_header_cannot_be_normalized(self):
        # Arrange
        image = bytes(0x100)

        # Act
        with pytest.raises(romtypes.RomTypeError) as raised:
            romtypes.normalized(romtypes.SNES, image)

        # Assert
        assert "no LoROM or HiROM header" in str(raised.value)

    def test_an_image_with_no_snes_header_cannot_be_normalized(self):
        # Arrange
        image = bytes(4 * BANK)

        # Act
        with pytest.raises(romtypes.RomTypeError) as raised:
            romtypes.normalized(romtypes.SNES, image)

        # Assert
        assert "no LoROM or HiROM header" in str(raised.value)


def interleaved_halves_inverse(image: bytes) -> bytes:
    banks = [image[at : at + BANK] for at in range(0, len(image), BANK)]
    half = len(banks) // 2
    return b"".join(banks[half + at] + banks[at] for at in range(half))


class TestN64:
    def test_a_v64_dump_is_byte_swapped_and_kept_that_way(self):
        # Arrange
        image = b"\x37\x80\x40\x12" + b"abcd"

        # Act
        found = romtypes.normalized(romtypes.N64, image)

        # Assert
        assert (found.data, found.restore(b"r")) == (b"\x80\x37\x12\x40badc", b"r")

    def test_a_z64_dump_is_used_as_it_is(self):
        # Arrange
        image = b"\x80\x37\x12\x40abcd"

        # Act
        found = romtypes.normalized(romtypes.N64, image)

        # Assert
        assert found.data == image


class TestHeaderedBySize:
    def test_a_game_boy_smartcard_header_is_removed(self):
        # Arrange
        image = bytearray(0x4000)
        image[0x104:0x108] = b"\xce\xed\x66\x66"

        # Act
        found = romtypes.normalized(romtypes.GB, bytes(0x200) + bytes(image))

        # Assert
        assert found.data == bytes(image)

    def test_a_game_boy_image_without_the_logo_cannot_be_normalized(self):
        # Arrange
        image = bytes(0x4000)

        # Act
        with pytest.raises(romtypes.RomTypeError) as raised:
            romtypes.normalized(romtypes.GB, image)

        # Assert
        assert "no Nintendo logo at 0x104" in str(raised.value)

    def test_a_pc_engine_header_is_removed_by_size(self):
        # Arrange
        image = body(0x2000)

        # Act
        found = romtypes.normalized(romtypes.PCE, bytes(0x200) + image)

        # Assert
        assert found.data == image

    def test_a_pc_engine_image_of_whole_banks_is_used_as_it_is(self):
        # Arrange
        image = body(0x2000)

        # Act
        found = romtypes.normalized(romtypes.PCE, image)

        # Assert
        assert found.data == image

    def test_a_lynx_header_is_removed_and_restored(self):
        # Arrange
        header = b"LYNX" + bytes(0x3C)

        # Act
        found = romtypes.normalized(romtypes.LYNX, header + body(32))

        # Assert
        assert found.data == body(32)
        assert found.restore(b"r") == header + b"r"

    def test_a_lynx_image_without_a_header_is_used_as_it_is(self):
        # Arrange
        image = body(32)

        # Act
        found = romtypes.normalized(romtypes.LYNX, image)

        # Assert
        assert found.data == image


class TestSega:
    @pytest.mark.parametrize(("kind", "sega_at"), [(romtypes.SMS, 0x7FF4), (romtypes.MD, 0x100)])
    def test_an_smd_dump_is_deinterleaved_into_a_plain_image(self, kind, sega_at):
        # Arrange
        image = bytearray(body(2 * 16 * KIB))
        image[sega_at : sega_at + 4] = b"SEGA"

        # Act
        found = romtypes.normalized(kind, smd(bytes(image)))

        # Assert
        assert found.data == bytes(image)

    @pytest.mark.parametrize(("kind", "sega_at"), [(romtypes.SMS, 0x7FF4), (romtypes.MD, 0x100)])
    def test_a_plain_image_is_used_as_it_is(self, kind, sega_at):
        # Arrange
        image = bytearray(body(2 * 16 * KIB))
        image[sega_at : sega_at + 4] = b"SEGA"

        # Act
        found = romtypes.normalized(kind, bytes(image))

        # Assert
        assert found.data == bytes(image)

    @pytest.mark.parametrize("kind", [romtypes.SMS, romtypes.MD])
    def test_an_image_in_neither_layout_cannot_be_normalized(self, kind):
        # Arrange
        image = bytes(2 * 16 * KIB)

        # Act
        with pytest.raises(romtypes.RomTypeError) as raised:
            romtypes.normalized(kind, image)

        # Assert
        assert "neither a plain image with SEGA nor an SMD dump" in str(raised.value)
