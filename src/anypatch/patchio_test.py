import struct

import pytest

from anypatch import patchio
from anypatch.patchio import Format

CRC_AT = 0x10


def image(size: int = 0x400, crc: tuple[int, int] = (0xCA12B547, 0x71FA4EE4)) -> bytes:
    out = bytearray(size)
    out[0:4] = b"\x80\x37\x12\x40"
    struct.pack_into(">II", out, CRC_AT, *crc)
    out[0x3C:0x3F] = b"NSE"
    out[0x40:] = bytes((at * 7) & 0xFF for at in range(0x40, size))
    return bytes(out)


def changed(before: bytes, at: int, data: bytes) -> bytes:
    return before[:at] + data + before[at + len(data) :]


class TestFormats:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("a.ips", Format.IPS),
            ("a.IPS", Format.IPS),
            ("a.zps", Format.ZPS),
            ("a.ip1", Format.ZPS),
            ("a.aps", Format.APS),
            ("a.ebp", Format.EBP),
            ("a.ups", Format.UPS),
            ("a.bps", Format.BPS),
            ("a.ppf", Format.PPF),
            ("a.rup", Format.RUP),
            ("a.bdf", Format.BDF),
            ("a.bsdiff", Format.BDF),
            ("a.xdelta", Format.XDELTA),
            ("a.vcdiff", Format.XDELTA),
            ("a.xd3", Format.XDELTA),
            ("a.delta", Format.XDELTA),
        ],
    )
    def test_an_output_path_names_its_format_by_extension(self, name, expected):
        # Arrange
        path = name

        # Act
        found = patchio.format_of(path)

        # Assert
        assert found == expected

    def test_an_unknown_extension_is_refused_with_the_known_ones(self):
        # Arrange
        path = "a.txt"

        # Act
        with pytest.raises(patchio.PatchError) as raised:
            patchio.format_of(path)

        # Assert
        assert ".ips" in str(raised.value) and ".xdelta" in str(raised.value)


TAIL = {Format.PAT: b""}


class TestRoundTrips:
    @pytest.mark.parametrize("kind", [one for one in patchio.WRITABLE if one is not Format.PMSR])
    def test_every_writable_format_turns_the_source_into_the_target(self, kind, tmp_path):
        # Arrange
        before = image()
        after = changed(before, 0x200, b"\xde\xad\xbe\xef") + TAIL.get(kind, b"tail")
        path = tmp_path / f"fix.{kind.value}"

        # Act
        written = patchio.write(path, kind, before, after, description="test")
        replayed = patchio.apply(before, patchio.read(path))

        # Assert
        assert replayed == after
        assert path in written


class TestReading:
    def test_a_zps_finds_its_header_beside_it_whatever_the_case(self, tmp_path):
        # Arrange
        before = image()
        patchio.write(tmp_path / "FIX.ZPS", Format.ZPS, before, changed(before, 0x200, b"\x01"))
        (tmp_path / "FIX.hdr").rename(tmp_path / "FIX.HDR")

        # Act
        patch = patchio.read(tmp_path / "FIX.ZPS")

        # Assert
        assert patch.binding == before[:64]

    def test_a_zps_without_a_header_applies_unchecked(self, tmp_path):
        # Arrange
        before = image()
        patchio.write(tmp_path / "fix.zps", Format.ZPS, before, changed(before, 0x200, b"\x01"))
        (tmp_path / "fix.hdr").unlink()

        # Act
        patch = patchio.read(tmp_path / "fix.zps")

        # Assert
        assert patch.binding is None
        assert patchio.apply(before, patch) == changed(before, 0x200, b"\x01")

    def test_the_contents_decide_the_format_not_the_name(self, tmp_path):
        # Arrange
        before = image()
        patchio.write(tmp_path / "fix.ips", Format.IPS, before, changed(before, 0x200, b"\x01"))
        (tmp_path / "fix.ips").rename(tmp_path / "fix.xdelta")

        # Act
        patch = patchio.read(tmp_path / "fix.xdelta")

        # Assert
        assert patch.format == Format.IPS

    def test_a_file_that_is_no_known_patch_is_refused(self, tmp_path):
        # Arrange
        path = tmp_path / "notes.ips"
        path.write_bytes(b"hello")

        # Act
        with pytest.raises(patchio.PatchError) as raised:
            patchio.read(path)

        # Assert
        assert str(raised.value) == (
            "notes.ips: not a patch in any format read here: "
            "IPS, IPS32, EBP, ZPS, APS, UPS, BPS, PPF, RUP, NINJA 1, PMSR, BDF, BSDIFF43, GDIFF, "
            "PAT, DPS, HDiffPatch, VPatch, JojoDiff or xdelta"
        )

    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            (b"IPS32EEOF", Format.IPS),
            (b"APS1" + bytes(8 + 0x10008), Format.APS_GBA),
            (b"APS10" + bytes(8), Format.APS),
            (b"UPS1", Format.UPS),
            (b"BPS1", Format.BPS),
            (b"PPF30", Format.PPF),
            (b"NINJA2", Format.RUP),
            (b"PMSR", Format.PMSR),
            (b"Yay0", Format.PMSR),
            (b"BSDIFF40", Format.BDF),
            (b"\xd6\xc3\xc4\x00", Format.XDELTA),
            (b"VPAT\x00\x00\x00\x80", Format.VPATCH),
            (b"MZ stub VPAT\x00\x00\x00\x80\x08\x00\x00\x00", Format.VPATCH),
        ],
    )
    def test_each_format_is_recognised_by_its_contents(self, body, expected, tmp_path):
        # Arrange
        path = tmp_path / "some.patch"
        path.write_bytes(body)

        # Act
        patch = patchio.read(path)

        # Assert
        assert patch.format == expected

    def test_a_jojodiff_patch_is_recognised_by_its_extension_alone(self, tmp_path):
        # Arrange
        path = tmp_path / "fix.jdf"
        path.write_bytes(b"PATCH")

        # Act
        patch = patchio.read(path)

        # Assert
        assert patch.format == Format.JOJODIFF

    def test_a_file_it_cannot_read_is_refused(self, tmp_path):
        # Arrange
        path = tmp_path / "absent.ips"

        # Act
        with pytest.raises(patchio.PatchError) as raised:
            patchio.read(path)

        # Assert
        assert "cannot read" in str(raised.value)


class TestApplying:
    @pytest.mark.parametrize("kind", [Format.APS, Format.ZPS])
    def test_a_bound_patch_on_another_dump_names_the_patch(self, kind, tmp_path):
        # Arrange
        before = image()
        path = tmp_path / f"fix.{kind.value}"
        patchio.write(path, kind, before, changed(before, 0x200, b"\x01"))
        other = image(crc=(1, 2))

        # Act
        with pytest.raises(patchio.PatchError) as raised:
            patchio.apply(other, patchio.read(path))

        # Assert
        assert str(raised.value).startswith(f"fix.{kind.value}: bound to")

    def test_a_damaged_patch_names_the_patch_and_the_fault(self, tmp_path):
        # Arrange
        path = tmp_path / "fix.ips"
        path.write_bytes(b"PATCH\x00\x00")

        # Act
        with pytest.raises(patchio.PatchError) as raised:
            patchio.apply(image(), patchio.read(path))

        # Assert
        assert str(raised.value) == "fix.ips: the patch ends inside the record at byte 5"

    def test_an_xdelta_on_the_wrong_dump_names_the_patch(self, tmp_path):
        # Arrange
        before = image()
        path = tmp_path / "fix.xdelta"
        patchio.write(path, Format.XDELTA, before, changed(before, 0x200, b"\x01"))

        # Act
        with pytest.raises(patchio.PatchError) as raised:
            patchio.apply(image(crc=(1, 2)), patchio.read(path))

        # Assert
        assert str(raised.value).startswith("fix.xdelta: the window at output")


class TestWriting:
    def test_a_zps_is_written_with_its_header_beside_it(self, tmp_path):
        # Arrange
        before = image()

        # Act
        written = patchio.write(tmp_path / "fix.zps", Format.ZPS, before, before)

        # Assert
        assert written == (tmp_path / "fix.zps", tmp_path / "fix.hdr")
        assert (tmp_path / "fix.hdr").read_bytes() == before[:64]

    def test_patch_bytes_are_computed_without_writing(self):
        # Arrange
        before = image()
        after = changed(before, 0x200, b"\x01")

        # Act
        files = patchio.encode(Format.IPS, before, after)

        # Assert
        assert files == {".ips": b"PATCH" + bytes([0, 2, 0, 0, 1, 1]) + b"EOF"}

    def test_a_format_that_cannot_express_the_change_says_which_to_use(self):
        # Arrange
        before = bytes(0x1000010)
        after = before[:-1] + b"\x01"

        # Act
        with pytest.raises(patchio.PatchError) as raised:
            patchio.encode(Format.ZPS, before, after)

        # Assert
        assert str(raised.value) == (
            "zps: ZPS is IPS, whose offsets and sizes stop below 16 MiB; use IPS32, APS or xdelta"
        )

    def test_an_ips_past_sixteen_mebibytes_comes_out_as_ips32(self):
        # Arrange
        before = bytes(0x1000010)
        after = before[:-1] + b"\x01"

        # Act
        files = patchio.encode(Format.IPS, before, after)

        # Assert
        assert files == {".ips": b"IPS32" + bytes([1, 0, 0, 0x0F, 0, 1, 1]) + b"EEOF"}

    def test_a_star_rod_patch_is_written_only_for_paper_mario(self):
        # Arrange
        before = image()

        # Act
        with pytest.raises(patchio.PatchError) as raised:
            patchio.encode(Format.PMSR, before, before + b"x")

        # Assert
        assert str(raised.value).startswith("pmsr: made for Paper Mario USA 1.0")

    def test_an_ebp_carries_the_description_as_metadata(self):
        # Arrange
        before = image()
        after = changed(before, 0x200, b"\x01")

        # Act
        files = patchio.encode(Format.EBP, before, after, description="hi")

        # Assert
        assert files[".ebp"].endswith(
            b'EOF{"patcher": "EBPatcher", "title": "", "author": "", "description": "hi"}'
        )


class TestPatWithoutItsExtension:
    def test_text_with_record_lines_is_read_as_pat(self):
        # Arrange
        body = b"Comparing files a and b\r\n00000000: 41 61\r\n"

        # Act
        found = patchio.identify(body, name="notes.bin")

        # Assert
        assert found is Format.PAT

    def test_a_pat_file_whose_comment_starts_with_patch_is_still_pat(self):
        # Arrange
        body = b"PATCH notes\r\n00000000: 41 61\r\n"

        # Act
        found = patchio.identify(body, name="fix.pat")

        # Assert
        assert found is Format.PAT
