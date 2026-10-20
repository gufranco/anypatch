import pytest

from anypatch import conflicts
from anypatch.conflicts import Change


def edited(data: bytes, at: int, new: bytes) -> bytes:
    return data[:at] + new + data[at + len(new) :]


BASE = bytes(range(64))


def change(name: str, at: int, new: bytes, base: bytes = BASE) -> Change:
    return conflicts.change(name, base, edited(base, at, new))


class TestChanges:
    def test_a_change_lists_each_differing_span_and_the_new_size(self):
        # Arrange
        after = edited(edited(BASE, 2, b"\xaa"), 10, b"\xbb\xcc") + b"tail"

        # Act
        found = conflicts.change("p", BASE, after)

        # Assert
        assert found == Change("p", ((2, b"\xaa"), (10, b"\xbb\xcc"), (64, b"tail")), 68)


class TestMerging:
    def test_patches_that_touch_different_bytes_compose(self):
        # Arrange
        changes = [change("a", 2, b"\xaa"), change("b", 30, b"\xbb")]

        # Act
        merged = conflicts.merge(BASE, BASE, changes)

        # Assert
        assert merged.image == edited(edited(BASE, 2, b"\xaa"), 30, b"\xbb")
        assert merged.applied == ("a", "b")
        assert merged.already == ()

    def test_identical_writes_to_one_byte_are_not_a_conflict(self):
        # Arrange
        changes = [change("a", 2, b"\xaa\xab"), change("b", 3, b"\xab")]

        # Act
        merged = conflicts.merge(BASE, BASE, changes)

        # Assert
        assert merged.image == edited(BASE, 2, b"\xaa\xab")

    def test_a_short_write_inside_a_longer_one_is_checked_before_the_next_span(self):
        # Arrange
        long = edited(BASE, 2, b"\x90" * 10)
        short = edited(edited(BASE, 4, b"\x90"), 40, b"\x41")
        changes = [conflicts.change("a", BASE, long), conflicts.change("b", BASE, short)]

        # Act
        merged = conflicts.merge(BASE, BASE, changes)

        # Assert
        assert merged.image == edited(long, 40, b"\x41")

    def test_different_writes_to_one_byte_are_refused_naming_both(self):
        # Arrange
        changes = [change("a", 2, b"\xaa\xab"), change("b", 3, b"\xcc")]

        # Act
        with pytest.raises(conflicts.ConflictError) as raised:
            conflicts.merge(BASE, BASE, changes)

        # Assert
        assert str(raised.value) == (
            "the patches conflict:\n  0x000003..0x000004: a writes ab, b writes cc"
        )

    def test_a_range_the_caller_leaves_out_is_not_compared(self):
        # Arrange
        changes = [change("a", 16, b"\x01"), change("b", 16, b"\x02")]

        # Act
        merged = conflicts.merge(BASE, BASE, changes, ignore=((16, 24),))

        # Assert
        assert merged.image[16] == 2

    def test_patches_that_resize_differently_are_refused(self):
        # Arrange
        changes = [
            conflicts.change("a", BASE, BASE + b"x"),
            conflicts.change("b", BASE, BASE[:60]),
        ]

        # Act
        with pytest.raises(conflicts.ConflictError) as raised:
            conflicts.merge(BASE, BASE, changes)

        # Assert
        assert "a makes it 0x41 bytes" in str(raised.value)
        assert "b makes it 0x3c bytes" in str(raised.value)

    def test_a_write_past_the_size_another_patch_sets_is_refused(self):
        # Arrange
        changes = [conflicts.change("a", BASE, BASE[:20]), change("b", 40, b"\x01")]

        # Act
        with pytest.raises(conflicts.ConflictError) as raised:
            conflicts.merge(BASE, BASE, changes)

        # Assert
        assert "b makes it 0x40 bytes" in str(raised.value)

    def test_a_patch_the_input_already_carries_is_reported_and_skipped(self):
        # Arrange
        carried = edited(BASE, 2, b"\xaa")
        changes = [change("a", 2, b"\xaa"), change("b", 30, b"\xbb")]

        # Act
        merged = conflicts.merge(carried, BASE, changes)

        # Assert
        assert merged.applied == ("b",)
        assert merged.already == ("a",)
        assert merged.image == edited(carried, 30, b"\xbb")

    def test_an_input_that_differs_from_the_clean_source_joins_the_check(self):
        # Arrange
        modified = edited(BASE, 2, b"\x77")
        changes = [change("a", 2, b"\xaa")]

        # Act
        with pytest.raises(conflicts.ConflictError) as raised:
            conflicts.merge(modified, BASE, changes)

        # Assert
        assert "the input: writes 77" not in str(raised.value)
        assert "the input writes 77, a writes aa" in str(raised.value)
