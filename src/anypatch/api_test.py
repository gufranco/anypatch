import pytest

from anypatch import api
from anypatch.conflicts import ConflictError
from anypatch.patchio import Format, PatchError

BASE = bytes((at * 7) & 0xFF for at in range(0x400))


def edited(data: bytes, at: int, new: bytes) -> bytes:
    return data[:at] + new + data[at + len(new) :]


def patch(name: str, after: bytes, kind: Format = Format.IPS) -> api.Patch:
    files = api.make(BASE, after, kind)
    return api.load(files[f".{kind.value}"], name=f"{name}.{kind.value}")


class TestTheCatalogue:
    def test_every_format_is_listed_once_with_what_it_supports(self):
        # Arrange
        expected = set(Format)

        # Act
        listed = api.formats()

        # Assert
        assert {one.format for one in listed} == expected
        assert len(listed) == len(expected)

    @pytest.mark.parametrize(
        ("kind", "reads", "writes"),
        [
            (Format.IPS, True, True),
            (Format.APS_GBA, True, True),
            (Format.PMSR, True, True),
            (Format.DLDI, True, False),
        ],
    )
    def test_each_format_says_what_it_reads_and_writes(self, kind, reads, writes):
        # Arrange
        listed = {one.format: one for one in api.formats()}

        # Act
        entry = listed[kind]

        # Assert
        assert (entry.reads, entry.writes) == (reads, writes)

    def test_the_description_names_what_binds_a_patch_to_its_source(self):
        # Arrange
        listed = {one.format: one for one in api.formats()}

        # Act
        entry = listed[Format.UPS]

        # Assert
        assert entry.name == "UPS"
        assert entry.binding == "CRC32 of the source and of the result"
        assert entry.extensions == (".ups",)


class TestIdentifying:
    def test_the_contents_decide_the_format(self):
        # Arrange
        data = api.make(BASE, edited(BASE, 4, b"\x01"), Format.BPS)[".bps"]

        # Act
        found = api.identify(data, name="looks-like.ips")

        # Assert
        assert found is Format.BPS

    def test_an_ips_body_named_zps_is_a_zps(self):
        # Arrange
        data = api.make(BASE, edited(BASE, 4, b"\x01"), Format.IPS)[".ips"]

        # Act
        found = api.identify(data, name="FIX.ZPS")

        # Assert
        assert found is Format.ZPS

    def test_unknown_bytes_are_refused(self):
        # Arrange
        data = b"hello"

        # Act
        with pytest.raises(PatchError) as raised:
            api.identify(data, name="notes.txt")

        # Assert
        assert str(raised.value).startswith("notes.txt: not a patch in any format read here")


class TestApplying:
    def test_patches_for_different_bytes_apply_together(self):
        # Arrange
        first = patch("a", edited(BASE, 4, b"\x01"))
        second = patch("b", edited(BASE, 40, b"\x02"), Format.BPS)

        # Act
        result = api.apply(BASE, [first, second])

        # Assert
        assert result.image == edited(edited(BASE, 4, b"\x01"), 40, b"\x02")
        assert result.applied == ("a.ips", "b.bps")

    def test_conflicting_patches_are_refused(self):
        # Arrange
        first = patch("a", edited(BASE, 4, b"\x01"))
        second = patch("b", edited(BASE, 4, b"\x02"))

        # Act
        with pytest.raises(ConflictError) as raised:
            api.apply(BASE, [first, second])

        # Assert
        assert "a.ips writes 01, b.ips writes 02" in str(raised.value)

    def test_a_patch_for_another_source_says_to_pass_the_clean_one(self):
        # Arrange
        checked = patch("c", edited(BASE, 4, b"\x01"), Format.UPS)
        other = edited(BASE, 100, b"\x09")

        # Act
        with pytest.raises(PatchError) as raised:
            api.apply(other, [checked])

        # Assert
        assert str(raised.value).startswith("c.ups: made for a 1,024-byte dump with CRC32")
        assert str(raised.value).endswith(api.CLEAN_HINT)

    def test_with_the_clean_source_the_input_joins_the_check(self):
        # Arrange
        checked = patch("c", edited(BASE, 4, b"\x01"), Format.UPS)
        modified = edited(BASE, 100, b"\x09")

        # Act
        result = api.apply(modified, [checked], clean=BASE)

        # Assert
        assert result.image == edited(modified, 4, b"\x01")

    def test_a_range_the_caller_leaves_out_is_not_compared(self):
        # Arrange
        first = patch("a", edited(BASE, 16, b"\x01"))
        second = patch("b", edited(BASE, 16, b"\x02"))

        # Act
        result = api.apply(BASE, [first, second], ignore=((16, 24),))

        # Assert
        assert result.image[16] == 2


class TestWriting:
    def test_merging_writes_one_patch_that_replays_every_input(self):
        # Arrange
        first = patch("a", edited(BASE, 4, b"\x01"))
        second = patch("b", edited(BASE, 40, b"\x02"))

        # Act
        files = api.merge(BASE, [first, second], Format.UPS)

        # Assert
        merged = api.load(files[".ups"], name="m.ups")
        assert api.apply(BASE, [merged]).image == edited(edited(BASE, 4, b"\x01"), 40, b"\x02")

    def test_converting_rewrites_a_patch_in_another_format(self):
        # Arrange
        original = patch("a", edited(BASE, 4, b"\x01") + b"tail")

        # Act
        files = api.convert(BASE, original, Format.BPS)

        # Assert
        converted = api.load(files[".bps"], name="a.bps")
        assert converted.format is Format.BPS
        assert api.apply(BASE, [converted]).image == edited(BASE, 4, b"\x01") + b"tail"

    def test_a_zps_comes_with_the_header_that_binds_it(self):
        # Arrange
        after = edited(BASE, 0x100, b"\x01")

        # Act
        files = api.make(BASE, after, Format.ZPS)

        # Assert
        assert files[".hdr"] == BASE[:64]
        loaded = api.load(files[".zps"], name="fix.zps", binding=files[".hdr"])
        assert loaded.binding == BASE[:64]
