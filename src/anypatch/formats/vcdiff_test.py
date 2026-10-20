import lzma
import struct
import zlib

import pytest

from anypatch.formats import imagesize, vcdiff
from anypatch.formats import xdelta_vectors_test_support as vectors

CASES = {case.name: case for case in vectors.cases()}


def plain_window(*, indicator: int = 0, target: bytes = b"ab", extra: bytes = b"") -> bytes:
    inst = bytes([1 + len(target)])
    body = (
        vcdiff.varint(len(target))
        + bytes([0])
        + vcdiff.varint(len(target))
        + vcdiff.varint(len(inst))
        + vcdiff.varint(0)
    )
    checksum = struct.pack(">I", zlib.adler32(target)) if indicator & vcdiff.VCD_ADLER32 else b""
    delta = body + checksum + target + inst + extra
    return bytes([indicator]) + vcdiff.varint(len(delta)) + delta


HEADER = vcdiff.MAGIC + bytes([0, 0])


class TestTheReferenceVectors:
    @pytest.mark.parametrize("name", sorted(CASES))
    def test_each_xdelta3_patch_rebuilds_its_target(self, name):
        # Arrange
        case = CASES[name]

        # Act
        target = vcdiff.apply(case.source, vectors.PATCHES[name])

        # Assert
        assert target == case.target

    def test_a_checksummed_patch_refuses_the_wrong_source(self):
        # Arrange
        case = CASES["windows"]
        wrong = bytes(b ^ 0x20 for b in case.source)

        # Act
        with pytest.raises(vcdiff.VcdiffError) as raised:
            vcdiff.apply(wrong, vectors.PATCHES["windows"])

        # Assert
        assert "does not match" in str(raised.value)

    def test_a_patch_reading_past_the_end_of_the_source_is_refused(self):
        # Arrange
        case = CASES["plain"]

        # Act
        with pytest.raises(vcdiff.VcdiffError) as raised:
            vcdiff.apply(case.source[:100], vectors.PATCHES["plain"])

        # Assert
        assert "past the end of this dump" in str(raised.value)


class TestBuilding:
    @pytest.mark.parametrize("name", sorted(CASES))
    def test_a_built_patch_rebuilds_the_target(self, name):
        # Arrange
        case = CASES[name]

        # Act
        patch = vcdiff.build(case.source, case.target, window=4096)

        # Assert
        assert vcdiff.apply(case.source, patch) == case.target

    def test_a_target_with_no_source_left_is_written_as_data_and_runs(self):
        # Arrange
        source = b"abcd"
        target = b"abcd" + b"\x00" * 40 + b"xyz"

        # Act
        patch = vcdiff.build(source, target, window=16)

        # Assert
        assert vcdiff.apply(source, patch) == target

    def test_an_empty_target_is_a_patch_with_no_windows(self):
        # Arrange
        source = b"abc"

        # Act
        patch = vcdiff.build(source, b"")

        # Assert
        assert patch == HEADER
        assert vcdiff.apply(source, patch) == b""

    def test_the_header_names_no_secondary_compressor(self):
        # Arrange
        source, target = b"a" * 64, b"b" * 64

        # Act
        patch = vcdiff.build(source, target)

        # Assert
        assert patch[:5] == HEADER


class TestRefusals:
    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            (b"PATCHEOF", "not a VCDIFF"),
            (vcdiff.MAGIC + b"\x01\x00", "version"),
            (vcdiff.MAGIC + b"\x00\x01\x07", "secondary compressor 7"),
            (vcdiff.MAGIC + b"\x00\x08", "header flags"),
            (HEADER + b"\x08", "window flags"),
            (HEADER + b"\x03", "both a source and a target"),
            (HEADER + b"\x00\x05", "ends"),
            (HEADER + plain_window(extra=b"!"), "delta length"),
            (HEADER + plain_window(indicator=vcdiff.VCD_TARGET), "past the end of the output"),
        ],
    )
    def test_a_damaged_patch_is_refused_with_its_reason(self, patch, message):
        # Arrange
        source = b"source"

        # Act
        with pytest.raises(vcdiff.VcdiffError) as raised:
            vcdiff.apply(source, patch)

        # Assert
        assert message in str(raised.value)

    def test_a_hand_built_window_with_a_checksum_applies(self):
        # Arrange
        patch = HEADER + plain_window(indicator=vcdiff.VCD_ADLER32, target=b"hello")

        # Act
        target = vcdiff.apply(b"", patch)

        # Assert
        assert target == b"hello"

    def test_a_target_window_copy_reads_earlier_output(self):
        # Arrange
        first = plain_window(target=b"abcd")
        inst = bytes([19]) + vcdiff.varint(4)
        addr = vcdiff.varint(0)
        segment = vcdiff.varint(4) + vcdiff.varint(0)
        body = (
            vcdiff.varint(4)
            + b"\x00"
            + vcdiff.varint(0)
            + vcdiff.varint(len(inst))
            + vcdiff.varint(len(addr))
        )
        delta = body + inst + addr
        second = bytes([vcdiff.VCD_TARGET]) + segment + vcdiff.varint(len(delta)) + delta

        # Act
        target = vcdiff.apply(b"", HEADER + first + second)

        # Assert
        assert target == b"abcdabcd"

    def test_a_copy_from_ahead_of_the_current_position_is_refused(self):
        # Arrange
        inst = bytes([19]) + vcdiff.varint(4)
        addr = vcdiff.varint(9)
        body = (
            vcdiff.varint(4)
            + b"\x00"
            + vcdiff.varint(0)
            + vcdiff.varint(len(inst))
            + vcdiff.varint(len(addr))
        )
        delta = body + inst + addr
        window = b"\x00" + vcdiff.varint(len(delta)) + delta

        # Act
        with pytest.raises(vcdiff.VcdiffError) as raised:
            vcdiff.apply(b"", HEADER + window)

        # Assert
        assert "copies from ahead" in str(raised.value)

    def test_a_window_whose_instructions_overrun_its_size_is_refused(self):
        # Arrange
        inst = bytes([1 + 3])
        body = vcdiff.varint(2) + b"\x00" + vcdiff.varint(3) + vcdiff.varint(1) + vcdiff.varint(0)
        delta = body + b"abc" + inst
        window = b"\x00" + vcdiff.varint(len(delta)) + delta

        # Act
        with pytest.raises(vcdiff.VcdiffError) as raised:
            vcdiff.apply(b"", HEADER + window)

        # Assert
        assert "writes past its declared size" in str(raised.value)

    def test_a_compressed_section_without_a_secondary_compressor_is_refused(self):
        # Arrange
        body = vcdiff.varint(0) + b"\x01" + vcdiff.varint(0) + vcdiff.varint(0) + vcdiff.varint(0)
        window = b"\x00" + vcdiff.varint(len(body)) + body

        # Act
        with pytest.raises(vcdiff.VcdiffError) as raised:
            vcdiff.apply(b"", HEADER + window)

        # Assert
        assert "no secondary compressor" in str(raised.value)

    def test_a_varint_longer_than_any_size_is_refused(self):
        # Arrange
        window = b"\x00" + b"\xff" * 12

        # Act
        with pytest.raises(vcdiff.VcdiffError) as raised:
            vcdiff.apply(b"", HEADER + window)

        # Assert
        assert "too long" in str(raised.value)


def compressed_window(data: bytes) -> bytes:
    inst = bytes([1 + 3])
    body = (
        vcdiff.varint(3) + b"\x01" + vcdiff.varint(len(data)) + vcdiff.varint(1) + vcdiff.varint(0)
    )
    delta = body + data + inst
    return b"\x00" + vcdiff.varint(len(delta)) + delta


LZMA_HEADER = vcdiff.MAGIC + bytes([0, vcdiff.VCD_SECONDARY, vcdiff.LZMA_ID])


class TestSecondarySections:
    def test_an_lzma_section_that_is_not_xz_is_refused(self):
        # Arrange
        patch = LZMA_HEADER + compressed_window(vcdiff.varint(3) + b"garbage!" * 8)

        # Act
        with pytest.raises(vcdiff.VcdiffError) as raised:
            vcdiff.apply(b"", patch)

        # Assert
        assert "does not decode" in str(raised.value)

    def test_an_lzma_section_shorter_than_it_declares_is_refused(self):
        # Arrange
        stream = lzma.compress(b"abc", format=lzma.FORMAT_XZ, check=lzma.CHECK_NONE)
        patch = LZMA_HEADER + compressed_window(vcdiff.varint(10) + stream)

        # Act
        with pytest.raises(vcdiff.VcdiffError) as raised:
            vcdiff.apply(b"", patch)

        # Assert
        assert "gave 3 bytes, not 10" in str(raised.value)


class TestWindowEdges:
    def test_data_left_over_after_the_instructions_is_refused(self):
        # Arrange
        inst = bytes([1 + 2])
        body = vcdiff.varint(2) + b"\x00" + vcdiff.varint(3) + vcdiff.varint(1) + vcdiff.varint(0)
        delta = body + b"abc" + inst
        window = b"\x00" + vcdiff.varint(len(delta)) + delta

        # Act
        with pytest.raises(vcdiff.VcdiffError) as raised:
            vcdiff.apply(b"", HEADER + window)

        # Assert
        assert "do not match its declared size" in str(raised.value)

    def test_a_patch_cut_inside_a_section_is_refused(self):
        # Arrange
        patch = vectors.PATCHES["plain"][:-3]

        # Act
        with pytest.raises(vcdiff.VcdiffError) as raised:
            vcdiff.apply(CASES["plain"].source, patch)

        # Assert
        assert "inside a" in str(raised.value)

    def test_a_short_literal_before_a_long_fill_is_written_as_data_then_a_run(self):
        # Arrange
        source = b"abcd" + b"\xff" * 36
        target = b"abcdxy" + b"\x00" * 30

        # Act
        patch = vcdiff.build(source, target)

        # Assert
        assert vcdiff.apply(source, patch) == target


def sized_window(size: int, inst: bytes, data: bytes) -> bytes:
    body = (
        vcdiff.varint(size)
        + bytes([0])
        + vcdiff.varint(len(data))
        + vcdiff.varint(len(inst))
        + vcdiff.varint(0)
    )
    delta = body + data + inst
    return bytes([0]) + vcdiff.varint(len(delta)) + delta


class TestSizesCheckedBeforeWork:
    def test_a_run_longer_than_its_window_is_refused_before_it_is_produced(self):
        # Arrange
        run = bytes([0]) + vcdiff.varint(1 << 40)
        patch = HEADER + sized_window(4, run, b"\x41")

        # Act
        with pytest.raises(vcdiff.VcdiffError) as raised:
            vcdiff.apply(b"", patch)

        # Assert
        assert "past its declared size 4" in str(raised.value)

    def test_a_window_past_the_ceiling_is_refused_before_it_is_decoded(self):
        # Arrange
        patch = HEADER + sized_window(1 << 40, b"", b"")

        # Act
        with pytest.raises(imagesize.ImageSizeError) as raised:
            vcdiff.apply(b"", patch)

        # Assert
        assert "1,099,511,627,776-byte result" in str(raised.value)

    def test_windows_that_add_up_past_the_ceiling_are_refused(self):
        # Arrange
        patch = HEADER + plain_window(target=b"ab") + sized_window(imagesize.LIMIT, b"", b"")

        # Act
        with pytest.raises(imagesize.ImageSizeError) as raised:
            vcdiff.apply(b"", patch)

        # Assert
        assert "1,073,741,826-byte result" in str(raised.value)


def code_string(table) -> bytes:
    columns = [[row[half][field] for row in table] for field in range(3) for half in range(2)]
    order = (0, 1, 2, 3, 4, 5)
    return b"".join(bytes(columns[at]) for at in order)


def add_window(target: bytes) -> bytes:
    inst = bytes([1]) + vcdiff.varint(len(target))
    body = (
        vcdiff.varint(len(target))
        + bytes([0])
        + vcdiff.varint(len(target))
        + vcdiff.varint(len(inst))
        + vcdiff.varint(0)
    )
    delta = body + target + inst
    return bytes([0]) + vcdiff.varint(len(delta)) + delta


def with_table(table, near: int, same: int, layout: str, nested_flags: int = 0) -> bytes:
    nested = vcdiff.MAGIC + bytes([0, nested_flags]) + add_window(code_string(table))
    head = vcdiff.MAGIC + bytes([0, vcdiff.VCD_CODETABLE])
    if layout == "rfc":
        data = bytes([near, same]) + nested
        return head + vcdiff.varint(len(data)) + data
    return head + vcdiff.varint(near) + vcdiff.varint(same) + nested


def window(size: int, inst: bytes, data: bytes, addr: bytes = b"", segment: bytes = b"") -> bytes:
    indicator = vcdiff.VCD_SOURCE if segment else 0
    body = (
        vcdiff.varint(size)
        + bytes([0])
        + vcdiff.varint(len(data))
        + vcdiff.varint(len(inst))
        + vcdiff.varint(len(addr))
    )
    delta = body + data + inst + addr
    return bytes([indicator]) + segment + vcdiff.varint(len(delta)) + delta


def rfc_table(data: bytes) -> bytes:
    return vcdiff.MAGIC + bytes([0, vcdiff.VCD_CODETABLE]) + vcdiff.varint(len(data)) + data


THREE_BYTE_ADD = 20
CUSTOM = (
    *vcdiff.TABLE[:THREE_BYTE_ADD],
    ((vcdiff.ADD, 3, 0), (vcdiff.NOOP, 0, 0)),
    *vcdiff.TABLE[THREE_BYTE_ADD + 1 :],
)


class TestApplicationCodeTables:
    @pytest.mark.parametrize("layout", ["rfc", "open-vcdiff"])
    def test_an_opcode_means_what_the_patch_table_says(self, layout):
        # Arrange
        patch = with_table(CUSTOM, 4, 3, layout) + window(3, bytes([THREE_BYTE_ADD]), b"xyz")

        # Act
        result = vcdiff.apply(b"", patch)

        # Assert
        assert result == b"xyz"

    def test_a_table_with_no_near_or_same_cache_copies_by_absolute_address(self):
        # Arrange
        copy_mode_zero = bytes([19]) + vcdiff.varint(3)
        segment = vcdiff.varint(4) + vcdiff.varint(0)
        body = window(3, copy_mode_zero, b"", vcdiff.varint(1), segment)
        patch = with_table(vcdiff.TABLE, 0, 0, "rfc") + body

        # Act
        result = vcdiff.apply(b"abcd", patch)

        # Assert
        assert result == b"bcd"

    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            (
                with_table(vcdiff.TABLE, 0, 0, "rfc")
                + window(4, bytes([19 + 2 * 16]) + vcdiff.varint(4), b"", vcdiff.varint(0)),
                "COPY mode 2 is past the 2 modes this code table allows",
            ),
            (
                with_table(vcdiff.TABLE, 4, 3, "rfc", nested_flags=vcdiff.VCD_CODETABLE),
                "a code table cannot carry another code table",
            ),
            (
                vcdiff.MAGIC + bytes([0, vcdiff.VCD_CODETABLE]) + vcdiff.varint(3) + b"\x04\x03!",
                "the code table data does not hold a VCDIFF delta",
            ),
            (
                with_table((*vcdiff.TABLE[:255], ((7, 0, 0), (0, 0, 0))), 4, 3, "rfc"),
                "opcode 255 names instruction type 7",
            ),
            (
                rfc_table(bytes([4, 3]) + vcdiff.MAGIC + bytes([0, 0]) + add_window(b"ab")),
                "the code table delta gives 2 bytes, not 1536",
            ),
            (
                vcdiff.MAGIC + bytes([0, vcdiff.VCD_CODETABLE]) + vcdiff.varint(300) + b"\x01",
                "cache sizes past 255",
            ),
        ],
        ids=["mode", "nested", "no-delta", "type", "short", "cache"],
    )
    def test_a_bad_code_table_is_refused(self, patch, message):
        # Arrange
        source = bytes(4)

        # Act
        with pytest.raises(vcdiff.VcdiffError) as raised:
            vcdiff.apply(source, patch)

        # Assert
        assert message in str(raised.value)
