import struct

import pytest

from n64_save_patches import zps

CRC_AT = 0x10


def image(crc: tuple[int, int] = (0x2337D8E8, 0x6B8E7CEC), size: int = 0x200) -> bytes:
    out = bytearray(size)
    out[0:4] = b"\x80\x37\x12\x40"
    struct.pack_into(">II", out, CRC_AT, *crc)
    out[0x40:] = bytes(at & 0xFF for at in range(0x40, size))
    return bytes(out)


def changed(before: bytes, at: int, data: bytes) -> bytes:
    return before[:at] + data + before[at + len(data) :]


class TestBuilding:
    def test_the_payload_is_ips_and_the_header_is_the_dumps_first_64_bytes(self):
        # Arrange
        before = image()
        after = changed(before, 0x100, b"\xde\xad")

        # Act
        payload, header = zps.build(before, after)

        # Assert
        assert payload.startswith(b"PATCH") and payload.endswith(b"EOF")
        assert header == before[:64]


class TestApplying:
    def test_a_bound_patch_replays_on_its_own_dump(self):
        # Arrange
        before = image()
        after = changed(before, 0x100, b"\xde\xad")
        payload, header = zps.build(before, after)

        # Act
        replayed = zps.apply(before, payload, header)

        # Assert
        assert replayed == after

    def test_a_patch_with_no_header_applies_unchecked(self):
        # Arrange
        before = image()
        after = changed(before, 0x100, b"\xde\xad")
        payload, _ = zps.build(before, after)

        # Act
        replayed = zps.apply(before, payload, None)

        # Assert
        assert replayed == after

    def test_a_patch_bound_to_another_dump_names_both_crc_pairs(self):
        # Arrange
        before = image()
        payload, header = zps.build(before, changed(before, 0x100, b"\x01"))
        other = image(crc=(0x11111111, 0x22222222))

        # Act
        with pytest.raises(zps.ZpsError) as raised:
            zps.apply(other, payload, header)

        # Assert
        assert str(raised.value) == "bound to 2337D8E8 6B8E7CEC, but this dump is 11111111 22222222"

    def test_a_header_of_the_wrong_size_is_refused(self):
        # Arrange
        before = image()
        payload, header = zps.build(before, changed(before, 0x100, b"\x01"))

        # Act
        with pytest.raises(zps.ZpsError) as raised:
            zps.apply(before, payload, header[:32])

        # Assert
        assert "64 bytes" in str(raised.value)


class TestLimits:
    def test_a_change_past_sixteen_mebibytes_is_refused_because_zps_is_classic_ips(self):
        # Arrange
        before = bytes(0x1000010)
        after = before[:-1] + b"\x01"

        # Act
        with pytest.raises(zps.ZpsError) as raised:
            zps.build(before, after)

        # Assert
        assert "use IPS32, APS or xdelta" in str(raised.value)
