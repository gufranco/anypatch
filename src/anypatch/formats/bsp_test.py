import hashlib
import struct

import pytest

from anypatch.formats import bsp, bspvm

SOURCE = b"ABCDEFGHIJKLMNOP"
TARGET = b"ABxyEFGHIJKLMNOP!!"


def word(value: int) -> bytes:
    return struct.pack("<I", value)


class TestWriting:
    def test_a_written_patch_checks_the_source_then_writes_each_change(self):
        # Arrange
        after = TARGET

        # Act
        patch = bsp.build(SOURCE, after)

        # Assert
        check = b"\x16\x00" + word(60) + b"\x5a\x00" + word(50) + b"\x1e" + word(18)
        first = b"\x60" + word(2) + b"\x7c" + word(129) + word(2)
        second = b"\x60" + word(16) + b"\x7c" + word(131) + word(2)
        code = check + first + second + b"\x06" + word(0)
        failure = b"\x68" + word(80) + b"\x06" + word(1)
        data = hashlib.sha1(SOURCE).digest() + bsp.WRONG_SOURCE + b"\x00" + b"xy!!"
        assert patch == code + failure + data

    @pytest.mark.parametrize(
        "after",
        [b"", b"AB", SOURCE, SOURCE[::-1], SOURCE + b"tail"],
        ids=["empty", "shrink", "same", "reversed", "grow"],
    )
    def test_a_written_patch_rebuilds_its_target(self, after):
        # Arrange
        patch = bsp.build(SOURCE, after)

        # Act
        result = bsp.apply(SOURCE, patch)

        # Assert
        assert result == after

    def test_a_written_patch_refuses_another_source_with_its_message(self):
        # Arrange
        patch = bsp.build(SOURCE, TARGET)

        # Act
        with pytest.raises(bspvm.BspError) as raised:
            bsp.apply(b"another file", patch)

        # Assert
        assert str(raised.value) == ("the patch exited with status 1: " + bsp.WRONG_SOURCE.decode())
