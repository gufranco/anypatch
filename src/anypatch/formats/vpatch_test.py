import hashlib
import struct
import zlib

import pytest

from anypatch.formats import imagesize, vpatch

SOURCE = b"ABCDEFGHIJKLMNOP"
TARGET = b"ABxyEFGHIJKLMNOP!!"


def md5(data: bytes) -> bytes:
    return hashlib.md5(data).digest()


def crc(data: bytes) -> bytes:
    return struct.pack("<I", zlib.crc32(data))


def copy(length: int, at: int, kind: int = 1) -> bytes:
    width = {1: "<B", 2: "<H", 3: "<I"}[kind]
    return bytes([kind]) + struct.pack(width, length) + struct.pack("<I", at)


def data(payload: bytes, kind: int = 5) -> bytes:
    width = {5: "<B", 6: "<H", 7: "<I"}[kind]
    return bytes([kind]) + struct.pack(width, len(payload)) + payload


def entry(blocks: list[bytes], before: bytes, after: bytes, *, sums=md5) -> bytes:
    body = b"".join(blocks)
    head = struct.pack("<I", len(blocks)) + sums(before) + sums(after)
    return head + struct.pack("<I", len(body)) + body


def vpat(*entries: bytes, md5_mode: bool = True) -> bytes:
    count = len(entries) | (vpatch.MD5_MODE if md5_mode else 0)
    return vpatch.MAGIC + struct.pack("<I", count) + b"".join(entries)


EDIT = [copy(2, 0), data(b"xy"), copy(12, 4), data(b"!!")]


class TestReading:
    def test_copies_and_literal_blocks_build_the_output_in_order(self):
        # Arrange
        patch = vpat(entry(EDIT, SOURCE, TARGET))

        # Act
        result = vpatch.apply(SOURCE, patch)

        # Assert
        assert result == TARGET

    @pytest.mark.parametrize("kind", [1, 2, 3])
    def test_every_copy_length_width_is_read(self, kind):
        # Arrange
        patch = vpat(entry([copy(4, 8, kind)], SOURCE, b"IJKL"))

        # Act
        result = vpatch.apply(SOURCE, patch)

        # Assert
        assert result == b"IJKL"

    @pytest.mark.parametrize("kind", [5, 6, 7])
    def test_every_literal_length_width_is_read(self, kind):
        # Arrange
        patch = vpat(entry([data(b"new", kind)], SOURCE, b"new"))

        # Act
        result = vpatch.apply(SOURCE, patch)

        # Assert
        assert result == b"new"

    def test_the_file_time_block_is_skipped(self):
        # Arrange
        stamp = bytes([vpatch.FILETIME]) + bytes(range(8))
        patch = vpat(entry([*EDIT, stamp], SOURCE, TARGET))

        # Act
        result = vpatch.apply(SOURCE, patch)

        # Assert
        assert result == TARGET

    def test_crc32_mode_checks_the_source_and_result_by_crc32(self):
        # Arrange
        patch = vpat(entry(EDIT, SOURCE, TARGET, sums=crc), md5_mode=False)

        # Act
        result = vpatch.apply(SOURCE, patch)

        # Assert
        assert result == TARGET

    def test_the_entry_made_for_this_source_is_chosen_among_several(self):
        # Arrange
        other = entry([data(b"zz")], b"another source", b"zz")
        patch = vpat(other, entry(EDIT, SOURCE, TARGET))

        # Act
        result = vpatch.apply(SOURCE, patch)

        # Assert
        assert result == TARGET

    def test_a_header_behind_the_pointer_at_the_end_is_found(self):
        # Arrange
        prefix = b"MZ installer stub"
        body = vpat(entry(EDIT, SOURCE, TARGET))
        patch = prefix + body + struct.pack("<I", len(prefix))

        # Act
        result = vpatch.apply(SOURCE, patch)

        # Assert
        assert result == TARGET

    def test_the_top_count_byte_is_reserved_and_ignored(self):
        # Arrange
        patch = bytearray(vpat(entry(EDIT, SOURCE, TARGET)))
        patch[7] = 0xFF

        # Act
        result = vpatch.apply(SOURCE, bytes(patch))

        # Assert
        assert result == TARGET


class TestRecognising:
    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            (vpat(), True),
            (b"stub" + vpat() + struct.pack("<I", 4), True),
            (b"stub" + struct.pack("<I", 0), False),
            (b"VPA", False),
            (b"stub" + struct.pack("<I", 1 << 30), False),
        ],
        ids=["start", "pointer", "pointer-to-junk", "short", "pointer-past-end"],
    )
    def test_a_vpatch_file_is_told_by_its_header_or_pointer(self, body, expected):
        # Arrange
        candidate = body

        # Act
        found = vpatch.matches(candidate)

        # Assert
        assert found is expected


class TestRefusals:
    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            (b"stub" + struct.pack("<I", 0), "no VPAT header"),
            (vpatch.MAGIC + b"\x01", "ends inside the patch count"),
            (vpat(entry(EDIT, SOURCE, TARGET))[:20], "ends inside the header of patch 1"),
            (vpat(entry(EDIT, SOURCE, TARGET))[:-1], "ends inside the body of patch 1"),
            (vpat(entry([b"\x09"], SOURCE, TARGET)), "unknown block type 9"),
            (vpat(entry([copy(0, 0)], SOURCE, b"")), "a block of length 0"),
            (vpat(entry([copy(4, 14)], SOURCE, TARGET)), "copies 4 bytes from 0xe"),
            (vpat(entry([data(b"xy")[:2]], SOURCE, TARGET)), "ends inside block 1"),
            (vpat(entry([b"\x01\x04"], SOURCE, TARGET)), "ends inside block 1"),
            (vpat(entry([b"\xff\x00"], SOURCE, TARGET)), "ends inside block 1"),
            (vpat(entry([b"\x01"], SOURCE, TARGET)), "ends inside block 1"),
            (vpat(entry([b""], SOURCE, TARGET)), "ends inside block 1"),
            (vpat(entry([data(b"xy")], SOURCE, TARGET)), "does not match the MD5"),
        ],
        ids=[
            "no-header",
            "short-count",
            "short-header",
            "short-body",
            "block-type",
            "zero-length",
            "copy-past-end",
            "short-literal",
            "short-copy",
            "short-time",
            "bare-copy-type",
            "missing-block",
            "result-sum",
        ],
    )
    def test_a_damaged_patch_is_refused(self, patch, message):
        # Arrange
        source = SOURCE

        # Act
        with pytest.raises(vpatch.VpatchError) as raised:
            vpatch.apply(source, patch)

        # Assert
        assert message in str(raised.value)

    def test_a_file_with_no_entry_for_this_source_names_how_many_it_holds(self):
        # Arrange
        patch = vpat(entry(EDIT, b"one", b"two"), entry(EDIT, b"three", b"four"))

        # Act
        with pytest.raises(vpatch.VpatchError) as raised:
            vpatch.apply(SOURCE, patch)

        # Assert
        assert str(raised.value) == "none of the 2 patches in this file was made for this source"

    def test_a_source_that_already_is_a_result_is_reported_as_patched(self):
        # Arrange
        patch = vpat(entry(EDIT, SOURCE, TARGET))

        # Act
        with pytest.raises(vpatch.VpatchError) as raised:
            vpatch.apply(TARGET, patch)

        # Assert
        assert str(raised.value) == "this source already is the result of a patch in this file"

    def test_a_crc32_result_mismatch_names_crc32(self):
        # Arrange
        patch = vpat(entry([data(b"xy")], SOURCE, TARGET, sums=crc), md5_mode=False)

        # Act
        with pytest.raises(vpatch.VpatchError) as raised:
            vpatch.apply(SOURCE, patch)

        # Assert
        assert "does not match the CRC32" in str(raised.value)

    def test_copies_past_the_ceiling_are_refused_before_allocating(self):
        # Arrange
        source = bytes(1 << 16)
        blocks = [copy(len(source), 0, 3)] * ((imagesize.LIMIT >> 16) + 1)
        patch = vpat(entry(blocks, source, TARGET))

        # Act
        with pytest.raises(ValueError) as raised:
            vpatch.apply(source, patch)

        # Assert
        assert "ceiling" in str(raised.value)


class TestWriting:
    def test_unchanged_spans_are_copied_and_changes_are_literal(self):
        # Arrange
        after = TARGET

        # Act
        patch = vpatch.build(SOURCE, after)

        # Assert
        assert patch == vpat(entry(EDIT, SOURCE, TARGET))

    @pytest.mark.parametrize(
        ("length", "copy_kind", "data_kind"),
        [(255, 1, 5), (256, 2, 6), (65535, 2, 6), (65536, 3, 7)],
        ids=["byte", "word-low", "word-high", "dword"],
    )
    def test_each_length_takes_the_narrowest_width(self, length, copy_kind, data_kind):
        # Arrange
        before = bytes(length)
        after = before + b"\x01" * length

        # Act
        patch = vpatch.build(before, after)

        # Assert
        blocks = [copy(length, 0, copy_kind), data(b"\x01" * length, data_kind)]
        assert patch == vpat(entry(blocks, before, after))

    @pytest.mark.parametrize(
        "after",
        [b"", b"AB", SOURCE, SOURCE[::-1], SOURCE + b"tail"],
        ids=["empty", "shrink", "same", "reversed", "grow"],
    )
    def test_a_written_patch_rebuilds_its_target(self, after):
        # Arrange
        patch = vpatch.build(SOURCE, after)

        # Act
        result = vpatch.apply(SOURCE, patch)

        # Assert
        assert result == after
