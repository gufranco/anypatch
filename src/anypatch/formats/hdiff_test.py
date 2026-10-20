import bz2
import lzma
import struct
import zlib

import pytest

from anypatch.formats import hdiff, imagesize


def varints(*values: int) -> bytes:
    return b"".join(hdiff.pack(value) for value in values)


def hdiff13(
    old: int,
    size: int,
    *,
    count: int = 0,
    covers: bytes = b"",
    ctrl: bytes = b"",
    code: bytes = b"",
    diff: bytes = b"",
) -> bytes:
    sections = (covers, ctrl, code, diff)
    sizes = b"".join(varints(len(one), 0) for one in sections)
    return b"HDIFF13&\x00" + varints(size, old, count) + sizes + b"".join(sections)


def compressed_patch(codec: bytes, packed: bytes, size: int) -> bytes:
    ctrl = hdiff.pack(size - 1, bits=2)
    head = b"HDIFF13&" + codec + b"\x00" + varints(size, 0, 0)
    return head + varints(0, 0, len(ctrl), 0, 0, 0, size, len(packed)) + ctrl + packed


def deflated(data: bytes) -> bytes:
    deflater = zlib.compressobj(9, zlib.DEFLATED, -15)
    return struct.pack("b", -15) + deflater.compress(data) + deflater.flush()


def lzma1(data: bytes) -> bytes:
    filters = [{"id": lzma.FILTER_LZMA1, "dict_size": 1 << 16, "lc": 3, "lp": 0, "pb": 2}]
    raw = lzma.compress(data, format=lzma.FORMAT_RAW, filters=filters)
    props = bytes([(2 * 5 + 0) * 9 + 3]) + struct.pack("<I", 1 << 16)
    return bytes([len(props)]) + props + raw


def lzma2(data: bytes) -> bytes:
    filters = [{"id": lzma.FILTER_LZMA2, "dict_size": 1 << 16}]
    return bytes([10]) + lzma.compress(data, format=lzma.FORMAT_RAW, filters=filters)


def zeros(length: int) -> bytes:
    return hdiff.pack(length - 1, tag=0, bits=2)


class TestNumbers:
    @pytest.mark.parametrize(
        ("value", "tag", "bits", "encoded"),
        [
            (0, 0, 0, b"\x00"),
            (0x7F, 0, 0, b"\x7f"),
            (0x80, 0, 0, b"\x81\x00"),
            (0x3FFF, 0, 0, b"\xff\x7f"),
            (5, 1, 1, b"\x85"),
            (0x40, 1, 1, b"\xc0\x40"),
            (3, 2, 2, b"\x83"),
        ],
    )
    def test_a_number_and_its_tag_are_packed_high_group_first(self, value, tag, bits, encoded):
        # Arrange
        expected = (value, len(encoded), tag)

        # Act
        packed = hdiff.pack(value, tag=tag, bits=bits)

        # Assert
        assert packed == encoded
        assert hdiff.unpack(encoded, 0, bits) == expected


class TestDamagedNumbers:
    @pytest.mark.parametrize(
        ("data", "message"),
        [(b"\x81", "the patch ends inside a number"), (b"\xff" * 12, "is too long")],
        ids=["cut", "long"],
    )
    def test_a_number_that_does_not_end_is_refused(self, data, message):
        # Arrange
        encoded = data

        # Act
        with pytest.raises(hdiff.HdiffError) as raised:
            hdiff.unpack(encoded, 0, 0)

        # Assert
        assert message in str(raised.value)


class TestHdiff13:
    def test_a_cover_adds_its_rle_bytes_to_the_old_bytes_and_gaps_come_from_the_diff(self):
        # Arrange
        source = b"ABCDEFGH"
        covers = hdiff.pack(2, tag=0, bits=1) + varints(1, 4)
        ctrl = zeros(1) + hdiff.pack(0, tag=2, bits=2) + zeros(4)
        patch = hdiff13(8, 6, count=1, covers=covers, ctrl=ctrl, code=b"\x01", diff=b"xy")

        # Act
        result = hdiff.apply(source, patch)

        # Assert
        assert result == b"xDDEFy"

    def test_rle_runs_of_255_subtract_one(self):
        # Arrange
        covers = hdiff.pack(0, tag=0, bits=1) + varints(0, 3)
        patch = hdiff13(3, 3, count=1, covers=covers, ctrl=hdiff.pack(2, tag=1, bits=2))

        # Act
        result = hdiff.apply(b"BCD", patch)

        # Assert
        assert result == b"ABC"

    def test_a_backward_cover_takes_the_sign_tag(self):
        # Arrange
        covers = hdiff.pack(2, tag=0, bits=1) + varints(0, 2)
        covers += hdiff.pack(4, tag=1, bits=1) + varints(0, 2)
        patch = hdiff13(4, 4, count=2, covers=covers, ctrl=zeros(4))

        # Act
        result = hdiff.apply(b"ABCD", patch)

        # Assert
        assert result == b"CDAB"


class TestCodecs:
    @pytest.mark.parametrize(
        ("codec", "packed"),
        [
            (b"zlib", deflated(b"hello")),
            (b"pzlib", deflated(b"hello")),
            (b"bz2", bz2.compress(b"hello")),
            (b"pbz2", bz2.compress(b"hel") + bz2.compress(b"lo")),
            (b"lzma", lzma1(b"hello")),
            (b"lzma2", lzma2(b"hello")),
        ],
    )
    def test_each_codec_decodes_its_section(self, codec, packed):
        # Arrange
        patch = compressed_patch(codec, packed, 5)

        # Act
        result = hdiff.apply(b"", patch)

        # Assert
        assert result == b"hello"

    @pytest.mark.parametrize(
        ("codec", "packed", "message"),
        [
            (b"zstd", b"\x00", "zstd sections need a codec the Python standard library lacks"),
            (b"brotli", b"\x00", "unknown codec 'brotli'"),
            (b"", b"\x00", "a section is compressed but the patch names no codec"),
            (b"zlib", b"\xf1not deflate", "a zlib section does not decompress"),
            (b"zlib", b"\x7f" + deflated(b"hello")[1:], "a zlib section does not decompress"),
            (b"bz2", b"not bzip2", "a bz2 section does not decompress"),
            (b"lzma", b"\x05\x5d\x00\x00\x01\x00garbage", "a lzma section does not decompress"),
            (b"lzma", b"\x09", "a lzma section ends inside its properties"),
            (b"lzma2", b"\x2ax", "a lzma2 section does not decompress"),
            (b"zlib", deflated(b"x"), "decodes to 1 bytes, not 5"),
        ],
        ids=[
            "zstd",
            "unknown",
            "no-codec",
            "zlib",
            "zlib-window",
            "bz2",
            "lzma",
            "props",
            "lzma2",
            "short",
        ],
    )
    def test_a_section_that_cannot_be_decoded_is_refused(self, codec, packed, message):
        # Arrange
        patch = compressed_patch(codec, packed, 5)

        # Act
        with pytest.raises(hdiff.HdiffError) as raised:
            hdiff.apply(b"", patch)

        # Assert
        assert message in str(raised.value)


def sf20(old: int, size: int, count: int, stream: bytes, packed: bytes = b"") -> bytes:
    codec = b"zlib" if packed else b""
    sizes = varints(size, old, count, 64, len(stream), len(packed))
    return b"HDIFFSF20&" + codec + b"\x00" + sizes + (packed or stream)


def sf20_cover(delta: int, gap: int, length: int, *, back: bool = False) -> bytes:
    return hdiff.pack(delta, tag=int(back), bits=1) + varints(gap, length)


class TestSingleStream:
    def test_gaps_are_inline_and_rle0_adds_bytes_to_covers(self):
        # Arrange
        covers = sf20_cover(2, 1, 4) + sf20_cover(2, 1, 0, back=True)
        rle = varints(1, 1) + b"\x01" + varints(2)
        stream = varints(len(covers), len(rle)) + covers + rle + b"x" + b"y"

        # Act
        result = hdiff.apply(b"ABCDEFGH", sf20(8, 6, 2, stream))

        # Assert
        assert result == b"xCEEFy"

    def test_a_compressed_stream_is_inflated_first(self):
        # Arrange
        final = sf20_cover(0, 3, 0)
        stream = varints(len(final), 0) + final + b"abc"

        # Act
        result = hdiff.apply(b"", sf20(0, 3, 1, stream, deflated(stream)))

        # Assert
        assert result == b"abc"

    @pytest.mark.parametrize(
        ("count", "stream", "size", "message"),
        [
            (
                2,
                varints(3, 0) + sf20_cover(0, 0, 0),
                0,
                "a zero-length cover comes before the last",
            ),
            (1, varints(9, 0), 0, "the patch ends inside a step"),
            (1, varints(3, 0) + sf20_cover(0, 0, 9), 9, "past the 4-byte source"),
            (1, varints(3, 2) + sf20_cover(0, 0, 2) + varints(0, 5), 2, "the rle0 data ends"),
            (1, varints(3, 0) + sf20_cover(0, 3, 0), 3, "the patch ends inside a gap"),
            (1, varints(3, 0) + sf20_cover(0, 0, 0), 2, "gives 0 bytes, not 2"),
            (1, varints(3, 0) + sf20_cover(0, 0, 0) + b"!", 0, "1 bytes follow the last step"),
        ],
        ids=["early-zero", "short-step", "past-source", "rle-short", "short-gap", "size", "extra"],
    )
    def test_a_damaged_stream_is_refused(self, count, stream, size, message):
        # Arrange
        patch = sf20(4, size, count, stream)

        # Act
        with pytest.raises(hdiff.HdiffError) as raised:
            hdiff.apply(b"ABCD", patch)

        # Assert
        assert message in str(raised.value)


class TestRefusals:
    @pytest.mark.parametrize(
        ("source", "patch", "message"),
        [
            (b"", b"HDIFF19&\x00", "only HDIFF13 and HDIFFSF20 are read"),
            (b"", b"PATCH", "not an HDiffPatch patch"),
            (b"", b"HDIFF13&zlib", "the codec name has no end"),
            (b"ABC", hdiff13(9, 0), "made for a 9-byte source, but this one is 3 bytes"),
            (b"", hdiff13(0, 0) + b"!", "1 bytes follow the last section"),
            (b"", hdiff13(0, 0)[:-2], "the patch ends inside a number"),
            (b"", hdiff13(0, 2, diff=b"xx")[:-1], "the patch ends inside a section"),
            (b"", hdiff13(0, 2, diff=b"x", ctrl=zeros(2)), "the gaps need more diff bytes"),
            (b"", hdiff13(0, 1, diff=b"xy", ctrl=zeros(1)), "1 diff bytes are left over"),
            (
                b"ABCD",
                hdiff13(4, 9, count=1, covers=hdiff.pack(0, bits=1) + varints(0, 9), ctrl=zeros(9)),
                "a cover of 9 bytes at 0x0 reaches past",
            ),
            (b"", hdiff13(0, 1, diff=b"x"), "the RLE stream ends before the output does"),
            (b"", hdiff13(0, 1, diff=b"x", ctrl=hdiff.pack(0, tag=2, bits=2)), "the RLE codes end"),
            (b"", hdiff13(0, 1, diff=b"x", ctrl=zeros(2)), "the RLE stream runs past the output"),
            (b"", hdiff13(0, 1, diff=b"x", ctrl=zeros(1) + zeros(1)), "runs past the output"),
            (
                b"ABCD",
                hdiff13(4, 2, count=1, covers=hdiff.pack(0, bits=1) + varints(0, 3), ctrl=zeros(2)),
                "a cover at 0x0 writes past the 2-byte result",
            ),
        ],
        ids=[
            "version",
            "magic",
            "codec-end",
            "old-size",
            "trailing",
            "short-number",
            "short-section",
            "gap-overrun",
            "diff-left",
            "cover-past",
            "rle-short",
            "rle-code-short",
            "rle-long",
            "rle-extra",
            "cover-past-result",
        ],
    )
    def test_a_damaged_or_mismatched_patch_is_refused(self, source, patch, message):
        # Arrange
        dump = source

        # Act
        with pytest.raises(hdiff.HdiffError) as raised:
            hdiff.apply(dump, patch)

        # Assert
        assert message in str(raised.value)

    def test_a_result_past_the_ceiling_is_refused_before_allocating(self):
        # Arrange
        patch = hdiff13(0, imagesize.LIMIT + 1)

        # Act
        with pytest.raises(imagesize.ImageSizeError) as raised:
            hdiff.apply(b"", patch)

        # Assert
        assert "ceiling" in str(raised.value)


class TestWriting:
    @pytest.mark.parametrize(
        ("before", "after"),
        [
            (b"", b""),
            (b"", b"grown from nothing"),
            (b"shrunk to nothing", b""),
            (bytes(range(256)) * 64, bytes(range(256)) * 60 + b"tail" * 300),
            (b"same bytes here", b"same bytes here"),
        ],
        ids=["empty", "grow-from-empty", "shrink-to-empty", "edited", "identical"],
    )
    def test_a_written_patch_rebuilds_its_target(self, before, after):
        # Arrange
        patch = hdiff.build(before, after)

        # Act
        result = hdiff.apply(before, patch)

        # Assert
        assert result == after

    def test_unchanged_runs_become_covers_and_changes_become_gap_data(self):
        # Arrange
        before = b"0123456789ABCDEF"
        after = b"01234567xx9ABCDEFtail"

        # Act
        patch = hdiff.build(before, after)

        # Assert
        assert patch.startswith(b"HDIFF13&\x00" + varints(len(after), len(before), 1))
        assert patch.endswith(b"xx9ABCDEFtail")
