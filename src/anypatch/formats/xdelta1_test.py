import gzip
import hashlib
import struct

import pytest

from anypatch.formats import imagesize, xdelta1

SOURCE = b"ABCDEFGHIJKLMNOP"
TARGET = b"ABxyEFGHIJKLMNOP!!"
CONTROL = struct.pack(">II", 0x8003, 0)


def md5(data: bytes) -> bytes:
    return hashlib.md5(data).digest()


def uint(value: int) -> bytes:
    groups = [(value >> shift) & 0x7F for shift in range(0, 35, 7)]
    used = max((index + 1 for index, group in enumerate(groups) if group), default=1)
    return bytes(
        group | (0x80 if index < used - 1 else 0) for index, group in enumerate(groups[:used])
    )


def text(value: bytes) -> bytes:
    return uint(len(value)) + value


def source_info(name: bytes, data: bytes, *, isdata: bool, sequential: bool) -> bytes:
    return text(name) + md5(data) + uint(len(data)) + bytes([isdata, sequential])


def control(target: bytes, sources: list[bytes], insts: list[tuple[int, int, int]]) -> bytes:
    body = md5(target) + uint(len(target)) + b"\x01" + uint(len(sources)) + b"".join(sources)
    body += uint(len(insts)) + b"".join(uint(a) + uint(b) + uint(c) for a, b, c in insts)
    return CONTROL + body


def patch(data: bytes, cont: bytes, *, flags: int = 0, magic: bytes = b"%XDZ004%") -> bytes:
    head = magic + struct.pack(">6I", flags, (6 << 16) | 6, 0, 0, 0, 0) + b"sourcetarget"
    return head + data + cont + struct.pack(">I", len(head) + len(data)) + magic


def edit(**options: int) -> bytes:
    data = b"xy!!"
    sources = [
        source_info(b"(patch data)", data, isdata=True, sequential=True),
        source_info(b"source", SOURCE, isdata=False, sequential=False),
    ]
    insts = [(1, 0, 2), (0, 0, 2), (1, 4, 12), (0, 0, 2)]
    return patch(data, control(TARGET, sources, insts), **options)


class TestReading:
    def test_copies_from_the_source_and_the_data_segment_build_the_output(self):
        # Arrange
        body = edit()

        # Act
        result = xdelta1.apply(SOURCE, body)

        # Assert
        assert result == TARGET

    def test_a_data_segment_that_is_not_sequential_uses_its_offsets(self):
        # Arrange
        data = b"!!xy"
        sources = [
            source_info(b"(patch data)", data, isdata=True, sequential=False),
            source_info(b"source", SOURCE, isdata=False, sequential=False),
        ]
        insts = [(1, 0, 2), (0, 2, 2), (1, 4, 12), (0, 0, 2)]
        body = patch(data, control(TARGET, sources, insts))

        # Act
        result = xdelta1.apply(SOURCE, body)

        # Assert
        assert result == TARGET

    def test_compressed_sections_are_gzip_streams(self):
        # Arrange
        plain = edit()
        data, cont = plain[44:48], plain[48:-12]
        squeezed = patch(gzip.compress(data), gzip.compress(cont), flags=xdelta1.PATCH_COMPRESSED)

        # Act
        result = xdelta1.apply(SOURCE, squeezed)

        # Assert
        assert result == TARGET

    def test_a_patch_made_without_verification_skips_the_md5(self):
        # Arrange
        sources = [source_info(b"source", SOURCE, isdata=False, sequential=False)]
        cont = CONTROL + bytes(16) + uint(4) + b"\x00" + uint(1) + b"".join(sources)
        body = patch(b"", cont + uint(1) + uint(0) + uint(2) + uint(4), flags=xdelta1.NO_VERIFY)

        # Act
        result = xdelta1.apply(SOURCE, body)

        # Assert
        assert result == SOURCE[2:6]

    def test_a_patch_with_only_the_data_segment_needs_no_source(self):
        # Arrange
        sources = [source_info(b"(patch data)", b"new", isdata=True, sequential=True)]
        body = patch(b"new", control(b"new", sources, [(0, 0, 3)]))

        # Act
        result = xdelta1.apply(b"anything", body)

        # Assert
        assert result == b"new"


class TestRefusals:
    @pytest.mark.parametrize(
        ("body", "message"),
        [
            (b"%XDZ003%" + bytes(40), "an xdelta 1.0.4 patch, %XDZ003%; only xdelta 1.1"),
            (b"%XDELTA%" + bytes(40), "an xdelta 0.14 patch, %XDELTA%"),
            (b"PATCH" + bytes(40), "not an xdelta 1 patch"),
            (edit()[:40], "too short to hold"),
            (edit()[:-1] + b"!", "the trailing magic is damaged"),
            (edit()[:-12] + struct.pack(">I", 9999) + b"%XDZ004%", "control offset"),
            (edit(flags=xdelta1.FROM_COMPRESSED), "gzip"),
            (edit(flags=xdelta1.TO_COMPRESSED), "gzip"),
            (patch(b"", struct.pack(">II", 0x2003, 0)), "an xdelta 1.0 control"),
            (patch(b"", struct.pack(">II", 0x0103, 0)), "not an xdelta control"),
            (patch(b"", CONTROL + bytes(10)), "the control ends early"),
            (patch(b"", CONTROL + bytes(16) + b"\xff" * 6), "a number longer than 32 bits"),
            (patch(b"", CONTROL + bytes(16) + b"\x80"), "the control ends early"),
            (edit(flags=xdelta1.PATCH_COMPRESSED), "not a gzip stream"),
        ],
        ids=[
            "older-version",
            "oldest-version",
            "magic",
            "short",
            "trailer",
            "control-offset",
            "from-compressed",
            "to-compressed",
            "version-0-control",
            "foreign-control",
            "short-control",
            "long-number",
            "number-cut",
            "bad-gzip",
        ],
    )
    def test_a_damaged_or_unsupported_patch_is_refused(self, body, message):
        # Arrange
        source = SOURCE

        # Act
        with pytest.raises(xdelta1.Xdelta1Error) as raised:
            xdelta1.apply(source, body)

        # Assert
        assert message in str(raised.value)

    @pytest.mark.parametrize(
        ("insts", "message"),
        [
            ([(2, 0, 1)], "names source 2, but the patch has 2"),
            ([(1, 10, 10)], "copies 10 bytes from 0xa, past the 16-byte source"),
            ([(0, 0, 5)], "copies 5 bytes from 0x0, past the 4-byte data segment"),
            ([(1, 0, 2)], "the result is 2 bytes, but the patch records 18"),
            ([(1, 0, 2), (0, 0, 2), (1, 4, 12), (0, 0, 1), (0, 0, 1)], "does not match the MD5"),
        ],
        ids=["index", "past-source", "past-data", "length", "md5"],
    )
    def test_an_instruction_that_cannot_be_followed_is_refused(self, insts, message):
        # Arrange
        data = b"xy!!"
        sources = [
            source_info(b"(patch data)", data, isdata=True, sequential=False),
            source_info(b"source", SOURCE, isdata=False, sequential=False),
        ]
        body = patch(data, control(TARGET, sources, insts))

        # Act
        with pytest.raises(xdelta1.Xdelta1Error) as raised:
            xdelta1.apply(SOURCE, body)

        # Assert
        assert message in str(raised.value)

    @pytest.mark.parametrize(
        ("sources", "message"),
        [
            (
                [source_info(b"s", SOURCE, isdata=False, sequential=False)] * 3,
                "3 sources; xdelta 1 reads at most a data segment and one source",
            ),
            (
                [source_info(b"s", SOURCE, isdata=False, sequential=False)] * 2,
                "two sources where the first is not the data segment",
            ),
            (
                [source_info(b"s", b"other length", isdata=False, sequential=False)],
                "made for a 12-byte source, but this one is 16 bytes",
            ),
        ],
        ids=["three", "two-without-data", "source-length"],
    )
    def test_sources_that_do_not_fit_the_patch_are_refused(self, sources, message):
        # Arrange
        body = patch(b"", control(TARGET, sources, []))

        # Act
        with pytest.raises(xdelta1.Xdelta1Error) as raised:
            xdelta1.apply(SOURCE, body)

        # Assert
        assert message in str(raised.value)

    def test_a_wrong_source_is_named_when_the_result_does_not_match(self):
        # Arrange
        other = b"ABCDEFGHIJKLMNOQ"
        body = edit()

        # Act
        with pytest.raises(xdelta1.Xdelta1Error) as raised:
            xdelta1.apply(other, body)

        # Assert
        assert "the source is not the file this patch was made for" in str(raised.value)

    def test_a_result_past_the_ceiling_is_refused_before_allocating(self):
        # Arrange
        sources = [source_info(b"s", SOURCE, isdata=False, sequential=False)]
        cont = CONTROL + bytes(16) + uint(imagesize.LIMIT + 1) + b"\x00" + uint(1) + sources[0]
        body = patch(b"", cont + uint(0))

        # Act
        with pytest.raises(ValueError) as raised:
            xdelta1.apply(SOURCE, body)

        # Assert
        assert "ceiling" in str(raised.value)

    def test_a_data_segment_declared_past_the_ceiling_is_refused_before_inflating(self):
        # Arrange
        sources = [source_info(b"(patch data)", b"", isdata=True, sequential=True)]
        declared = sources[0][:-3] + uint(imagesize.LIMIT + 1) + b"\x01\x01"
        body = patch(
            gzip.compress(b"x"),
            gzip.compress(control(b"", [declared], [])),
            flags=xdelta1.PATCH_COMPRESSED,
        )

        # Act
        with pytest.raises(ValueError) as raised:
            xdelta1.apply(SOURCE, body)

        # Assert
        assert "ceiling" in str(raised.value)

    def test_a_data_segment_that_inflates_past_its_declared_size_is_refused(self):
        # Arrange
        sources = [source_info(b"(patch data)", b"four", isdata=True, sequential=True)]
        cont = gzip.compress(control(b"four", sources, [(0, 0, 4)]))
        body = patch(gzip.compress(bytes(100)), cont, flags=xdelta1.PATCH_COMPRESSED)

        # Act
        with pytest.raises(xdelta1.Xdelta1Error) as raised:
            xdelta1.apply(SOURCE, body)

        # Assert
        assert "inflates past the 4 bytes the patch declares" in str(raised.value)


class TestWriting:
    def test_a_written_patch_copies_unchanged_spans_and_stores_changes_as_data(self):
        # Arrange
        after = TARGET

        # Act
        body = xdelta1.build(SOURCE, after)

        # Assert
        assert body == edit()

    @pytest.mark.parametrize(
        "after",
        [b"", b"AB", SOURCE, SOURCE[::-1], SOURCE + b"tail"],
        ids=["empty", "shrink", "same", "reversed", "grow"],
    )
    def test_a_written_patch_rebuilds_its_target(self, after):
        # Arrange
        body = xdelta1.build(SOURCE, after)

        # Act
        result = xdelta1.apply(SOURCE, body)

        # Assert
        assert result == after

    @pytest.mark.parametrize(
        ("before", "after", "listed"),
        [(b"", b"fresh", 1), (SOURCE, b"", 0), (SOURCE, SOURCE, 1)],
        ids=["data-alone", "nothing", "source-alone"],
    )
    def test_only_the_sources_an_instruction_reads_are_listed(self, before, after, listed):
        # Arrange
        body = xdelta1.build(before, after)
        control_at = struct.unpack(">I", body[-12:-8])[0]

        # Act
        sources = xdelta1.control_of(body[control_at:-12]).sources

        # Assert
        assert len(sources) == listed
