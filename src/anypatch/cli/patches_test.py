import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from anypatch import api
from anypatch.cli.main import app
from anypatch.formats import bsp_vectors_test_support as vectors
from anypatch.patchio import WRITABLE, Format

RUNNER = CliRunner()
BASE = bytes((at * 7) & 0xFF for at in range(0x400))


TAIL = {Format.PAT: b""}


def edited(data: bytes, at: int, new: bytes) -> bytes:
    return data[:at] + new + data[at + len(new) :]


def files(tmp_path: Path, **named: bytes) -> dict[str, str]:
    for name, data in named.items():
        (tmp_path / name.replace("_", ".")).write_bytes(data)
    return {name: str(tmp_path / name.replace("_", ".")) for name in named}


def run(*args: str):
    return RUNNER.invoke(app, list(args))


class TestMake:
    @pytest.mark.parametrize("kind", [one for one in WRITABLE if one is not Format.PMSR])
    def test_the_command_writes_the_bytes_the_library_returns(self, kind, tmp_path):
        # Arrange
        after = edited(BASE, 0x200, b"\xde\xad") + TAIL.get(kind, b"tail")
        paths = files(tmp_path, before_bin=BASE, after_bin=after)
        target = tmp_path / f"fix.{kind.value}"

        # Act
        result = run(
            "make",
            paths["before_bin"],
            paths["after_bin"],
            "-o",
            str(target),
            "--format",
            kind.value,
        )

        # Assert
        assert result.exit_code == 0, result.output
        expected = api.make(BASE, after, kind)
        assert target.read_bytes() == expected[f".{kind.value}"]

    def test_a_zps_is_written_with_its_header(self, tmp_path):
        # Arrange
        paths = files(tmp_path, before_bin=BASE, after_bin=edited(BASE, 0x100, b"\x01"))

        # Act
        result = run("make", paths["before_bin"], paths["after_bin"], "-o", str(tmp_path / "f.zps"))

        # Assert
        assert result.exit_code == 0
        assert (tmp_path / "f.hdr").read_bytes() == BASE[:64]

    def test_the_format_option_overrides_the_extension(self, tmp_path):
        # Arrange
        paths = files(tmp_path, before_bin=BASE, after_bin=edited(BASE, 4, b"\x01"))
        target = tmp_path / "fix.patch"

        # Act
        result = run(
            "make", paths["before_bin"], paths["after_bin"], "-o", str(target), "--format", "bps"
        )

        # Assert
        assert result.exit_code == 0
        assert target.read_bytes().startswith(b"BPS1")

    def test_an_unknown_extension_without_a_format_writes_nothing(self, tmp_path):
        # Arrange
        paths = files(tmp_path, before_bin=BASE, after_bin=BASE)
        target = tmp_path / "fix.txt"

        # Act
        result = run("make", paths["before_bin"], paths["after_bin"], "-o", str(target))

        # Assert
        assert result.exit_code == 1
        assert "unknown patch extension" in result.output
        assert not target.exists()

    def test_a_star_rod_patch_needs_paper_mario(self, tmp_path):
        # Arrange
        paths = files(tmp_path, before_bin=BASE, after_bin=BASE)

        # Act
        result = run(
            "make",
            paths["before_bin"],
            paths["after_bin"],
            "-o",
            str(tmp_path / "x"),
            "--format",
            "pmsr",
        )

        # Assert
        assert result.exit_code == 1
        assert "pmsr: made for Paper Mario USA 1.0" in result.output

    def test_a_file_it_cannot_read_is_reported(self, tmp_path):
        # Arrange
        missing = str(tmp_path / "absent.bin")

        # Act
        result = run("make", missing, missing, "-o", str(tmp_path / "x.ips"))

        # Assert
        assert result.exit_code == 1
        assert "cannot read" in result.output


class TestApply:
    def test_patches_apply_together_and_the_image_is_written(self, tmp_path):
        # Arrange
        one = api.make(BASE, edited(BASE, 4, b"\x01"), Format.IPS)[".ips"]
        two = api.make(BASE, edited(BASE, 40, b"\x02"), Format.UPS)[".ups"]
        paths = files(tmp_path, base_bin=BASE, one_ips=one, two_ups=two)
        out = tmp_path / "out.bin"

        # Act
        result = run("apply", paths["base_bin"], paths["one_ips"], paths["two_ups"], "-o", str(out))

        # Assert
        assert result.exit_code == 0
        assert out.read_bytes() == edited(edited(BASE, 4, b"\x01"), 40, b"\x02")
        assert "applied        one.ips, two.ups" in result.output

    def test_a_conflict_is_refused_and_nothing_is_written(self, tmp_path):
        # Arrange
        one = api.make(BASE, edited(BASE, 4, b"\x01"), Format.IPS)[".ips"]
        two = api.make(BASE, edited(BASE, 4, b"\x02"), Format.IPS)[".ips"]
        paths = files(tmp_path, base_bin=BASE, one_ips=one, two_ips=two)
        out = tmp_path / "out.bin"

        # Act
        result = run("apply", paths["base_bin"], paths["one_ips"], paths["two_ips"], "-o", str(out))

        # Assert
        assert result.exit_code == 1
        assert "the patches conflict" in result.output
        assert not out.exists()

    def test_with_the_clean_source_a_patched_input_is_accepted(self, tmp_path):
        # Arrange
        checked = api.make(BASE, edited(BASE, 4, b"\x01"), Format.UPS)[".ups"]
        modified = edited(BASE, 100, b"\x09")
        paths = files(tmp_path, base_bin=BASE, mod_bin=modified, fix_ups=checked)
        out = tmp_path / "out.bin"

        # Act
        result = run(
            "apply",
            paths["mod_bin"],
            paths["fix_ups"],
            "-o",
            str(out),
            "--clean",
            paths["base_bin"],
        )

        # Assert
        assert result.exit_code == 0
        assert out.read_bytes() == edited(modified, 4, b"\x01")

    def test_a_patch_already_in_the_input_is_reported(self, tmp_path):
        # Arrange
        after = edited(BASE, 4, b"\x01")
        fix = api.make(BASE, after, Format.UPS)[".ups"]
        paths = files(tmp_path, after_bin=after, fix_ups=fix)

        # Act
        result = run("apply", paths["after_bin"], paths["fix_ups"], "-o", str(tmp_path / "o.bin"))

        # Assert
        assert result.exit_code == 0
        assert "already in     fix.ups" in result.output


class TestBspMenus:
    def test_a_choice_answers_the_menu_of_a_bsp(self, tmp_path):
        # Arrange
        paths = files(tmp_path, base_bin=vectors.INPUT, menu_bsp=vectors.PATCHES["menu"])
        out = tmp_path / "out.bin"

        # Act
        result = run("apply", paths["base_bin"], paths["menu_bsp"], "--choice", "1", "-o", str(out))

        # Assert
        assert result.exit_code == 0, result.output
        assert out.read_bytes() == vectors.RESULTS["menu"]

    def test_a_menu_without_a_choice_lists_its_options(self, tmp_path):
        # Arrange
        paths = files(tmp_path, base_bin=vectors.INPUT, menu_bsp=vectors.PATCHES["menu"])

        # Act
        result = run("apply", paths["base_bin"], paths["menu_bsp"], "-o", str(tmp_path / "o"))

        # Assert
        assert result.exit_code == 1
        assert "choose between: First, Second, Third" in result.output


class TestMergeAndConvert:
    def test_merge_writes_one_patch_for_every_input(self, tmp_path):
        # Arrange
        one = api.make(BASE, edited(BASE, 4, b"\x01"), Format.IPS)[".ips"]
        two = api.make(BASE, edited(BASE, 40, b"\x02"), Format.BPS)[".bps"]
        paths = files(tmp_path, base_bin=BASE, one_ips=one, two_bps=two)
        target = tmp_path / "both.ups"

        # Act
        result = run(
            "merge", paths["base_bin"], paths["one_ips"], paths["two_bps"], "-o", str(target)
        )

        # Assert
        assert result.exit_code == 0
        merged = api.load(target.read_bytes(), name="both.ups")
        assert api.apply(BASE, [merged]).image == edited(edited(BASE, 4, b"\x01"), 40, b"\x02")

    def test_convert_rewrites_a_patch_in_the_format_the_extension_names(self, tmp_path):
        # Arrange
        one = api.make(BASE, edited(BASE, 4, b"\x01"), Format.IPS)[".ips"]
        paths = files(tmp_path, base_bin=BASE, one_ips=one)
        target = tmp_path / "one.xdelta"

        # Act
        result = run("convert", paths["base_bin"], paths["one_ips"], "-o", str(target))

        # Assert
        assert result.exit_code == 0
        assert api.identify(target.read_bytes(), name="one.xdelta") is Format.XDELTA

    def test_convert_reports_a_patch_that_does_not_fit_the_source(self, tmp_path):
        # Arrange
        checked = api.make(BASE, edited(BASE, 4, b"\x01"), Format.UPS)[".ups"]
        paths = files(tmp_path, other_bin=edited(BASE, 9, b"\x09"), fix_ups=checked)

        # Act
        result = run("convert", paths["other_bin"], paths["fix_ups"], "-o", str(tmp_path / "x.bps"))

        # Assert
        assert result.exit_code == 1
        assert "fix.ups: made for" in result.output


class TestRevert:
    def test_revert_writes_the_source_a_patch_was_made_from(self, tmp_path):
        # Arrange
        after = edited(BASE, 4, b"\x01")
        body = api.make(BASE, after, Format.UPS)[".ups"]
        paths = files(tmp_path, after_bin=after, fix_ups=body)
        out = tmp_path / "back.bin"

        # Act
        result = run("revert", paths["after_bin"], paths["fix_ups"], "-o", str(out))

        # Assert
        assert result.exit_code == 0, result.output
        assert out.read_bytes() == BASE

    def test_revert_refuses_a_patch_with_no_way_back(self, tmp_path):
        # Arrange
        body = api.make(BASE, edited(BASE, 4, b"\x01"), Format.IPS)[".ips"]
        paths = files(tmp_path, base_bin=BASE, fix_ips=body)
        out = tmp_path / "back.bin"

        # Act
        result = run("revert", paths["base_bin"], paths["fix_ips"], "-o", str(out))

        # Assert
        assert result.exit_code == 1
        assert "IPS patches carry no way back" in result.output
        assert not out.exists()


class TestDescribing:
    def test_info_names_the_format_and_what_binds_it(self, tmp_path):
        # Arrange
        fix = api.make(BASE, edited(BASE, 4, b"\x01"), Format.BPS)[".bps"]
        paths = files(tmp_path, fix_bps=fix)

        # Act
        result = run("info", paths["fix_bps"])

        # Assert
        assert result.exit_code == 0
        assert result.output.splitlines() == [
            "format         BPS",
            "bound by       CRC32 of the source and of the result",
            f"size           {len(fix):,} bytes",
        ]

    def test_info_as_json(self, tmp_path):
        # Arrange
        fix = api.make(BASE, edited(BASE, 4, b"\x01"), Format.IPS)[".ips"]
        paths = files(tmp_path, fix_ips=fix)

        # Act
        result = run("info", paths["fix_ips"], "--json")

        # Assert
        assert json.loads(result.output) == {
            "format": "ips",
            "name": "IPS",
            "binding": "nothing",
            "size": len(fix),
        }

    def test_info_refuses_a_file_that_is_no_patch(self, tmp_path):
        # Arrange
        paths = files(tmp_path, notes_txt=b"hello")

        # Act
        result = run("info", paths["notes_txt"])

        # Assert
        assert result.exit_code == 1
        assert "not a patch in any format read here" in result.output

    def test_formats_lists_every_format(self):
        # Arrange
        args = ("formats",)

        # Act
        result = run(*args)

        # Assert
        assert result.exit_code == 0
        assert len(result.output.splitlines()) == len(Format)
        assert result.output.splitlines()[0].startswith("IPS ")

    def test_formats_as_json(self):
        # Arrange
        args = ("formats", "--json")

        # Act
        result = run(*args)

        # Assert
        listed = json.loads(result.output)
        assert listed[0] == {
            "format": "ips",
            "name": "IPS",
            "extensions": [".ips"],
            "reads": True,
            "writes": True,
            "binding": "nothing",
        }
