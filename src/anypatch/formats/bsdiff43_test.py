import bz2

import pytest

from anypatch.formats import bdf, bsdiff43, imagesize


def patch_of(size: int, stream: bytes) -> bytes:
    return bsdiff43.MAGIC + bdf.offt(size) + bz2.compress(stream)


def triple(adding: int, extra: int, seek: int = 0) -> bytes:
    return bdf.offt(adding) + bdf.offt(extra) + bdf.offt(seek)


class TestWriting:
    def test_one_triple_carries_the_difference_and_the_tail(self):
        # Arrange
        before, after = b"abc", b"abdXY"

        # Act
        patch = bsdiff43.build(before, after)

        # Assert
        assert patch == patch_of(5, triple(3, 2) + bytes([0, 0, 1]) + b"XY")

    @pytest.mark.parametrize(
        ("before", "after"),
        [
            (b"", b"grown from nothing"),
            (b"shrunk to nothing", b""),
            (bytes(range(256)) * 64, bytes(range(255, -1, -1)) * 60),
            (b"same", b"same"),
        ],
        ids=["grow-from-empty", "shrink-to-empty", "reversed", "identical"],
    )
    def test_a_written_patch_rebuilds_its_target(self, before, after):
        # Arrange
        patch = bsdiff43.build(before, after)

        # Act
        result = bsdiff43.apply(before, patch)

        # Assert
        assert result == after


class TestReading:
    def test_a_backward_seek_reads_earlier_source_bytes(self):
        # Arrange
        stream = triple(2, 0, -2) + bytes(2) + triple(2, 0) + bytes(2)

        # Act
        result = bsdiff43.apply(b"ab", patch_of(4, stream))

        # Assert
        assert result == b"abab"

    def test_a_triple_that_writes_nothing_is_allowed_as_mendsley_bsdiff_emits_it(self):
        # Arrange
        stream = triple(0, 0, 1) + triple(1, 0) + bytes(1)

        # Act
        result = bsdiff43.apply(b"xy", patch_of(1, stream))

        # Assert
        assert result == b"y"


class TestDamage:
    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            (b"BSDIFF40" + bytes(24), "not a BSDIFF43 patch"),
            (bsdiff43.MAGIC + bytes(4), "too short to hold"),
            (bsdiff43.MAGIC + bdf.offt(-1), "a negative size"),
            (bsdiff43.MAGIC + bdf.offt(1) + b"not bzip2 at all", "does not decompress"),
            (patch_of(1, triple(1, 0)[:10]), "ends inside a control triple"),
            (patch_of(4, triple(4, 0) + bytes(2)), "ends inside the diff"),
            (patch_of(4, triple(0, 4) + b"ab"), "ends inside the extra"),
            (patch_of(2, triple(-1, 0)), "a negative length"),
            (patch_of(2, triple(3, 0) + bytes(3)), "writes past the 2-byte target"),
            (patch_of(1, triple(1, 0) + bytes(1) + b"left"), "4 bytes follow the last"),
            (patch_of(1, triple(1, 0) + bytes(1)) + b"trailing", "8 bytes follow the stream"),
            (patch_of(1, triple(0, 0) * 3), "more control triples than"),
        ],
        ids=[
            "magic",
            "short-header",
            "negative-size",
            "not-bzip2",
            "short-triple",
            "short-diff",
            "short-extra",
            "negative-length",
            "past-target",
            "leftover-stream",
            "leftover-file",
            "no-progress",
        ],
    )
    def test_a_damaged_patch_is_refused(self, patch, message):
        # Arrange
        source = b"abcd"

        # Act
        with pytest.raises((bsdiff43.Bsdiff43Error, bdf.BdfError)) as raised:
            bsdiff43.apply(source, patch)

        # Assert
        assert message in str(raised.value)

    def test_a_size_past_the_ceiling_is_refused_before_decompressing(self):
        # Arrange
        patch = bsdiff43.MAGIC + bdf.offt(imagesize.LIMIT + 1) + b"never read"

        # Act
        with pytest.raises(imagesize.ImageSizeError) as raised:
            bsdiff43.apply(b"", patch)

        # Assert
        assert "ceiling" in str(raised.value)
