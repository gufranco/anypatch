import pytest

from anypatch.formats import pat

WORKED = b"Comparing files GAME.ROM and EDITED.ROM\r\n00000001: 42 62\r\n0000000A: 4B 6B\r\n"
SOURCE = b"ABCDEFGHIJKL"


class TestReading:
    def test_each_record_changes_its_byte(self):
        # Arrange
        patch = WORKED

        # Act
        result = pat.apply(SOURCE, patch)

        # Assert
        assert result == b"AbCDEFGHIJkL"

    def test_lowercase_hex_and_unix_line_ends_are_read(self):
        # Arrange
        patch = b"0000000a: 4b 6b\n"

        # Act
        result = pat.apply(SOURCE, patch)

        # Assert
        assert result == b"ABCDEFGHIJkL"

    def test_a_byte_already_changed_is_left_as_it_is(self):
        # Arrange
        patched = b"AbCDEFGHIJKL"

        # Act
        result = pat.apply(patched, WORKED)

        # Assert
        assert result == b"AbCDEFGHIJkL"

    def test_lines_that_are_not_records_are_comments(self):
        # Arrange
        patch = b"FireFlower patch by someone\r\n\r\n00000000: 41 61\r\nFC: no differences\r\n"

        # Act
        result = pat.apply(SOURCE, patch)

        # Assert
        assert result == b"aBCDEFGHIJKL"


class TestRefusals:
    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            (b"00000001: 58 59\r\n", "at 0x1 this image holds 42, which is neither 58 nor 59"),
            (b"00000100: 41 42\r\n", "a record at 0x100 lies past the 12-byte image"),
            (b"no records at all\r\n", "not a PAT patch: no line reads OOOOOOOO: SS MM"),
            (b"\xff\xfe binary\r\n00000000: 41 61\r\n", "not a PAT patch: it is not text"),
        ],
        ids=["wrong-byte", "past-end", "no-records", "binary"],
    )
    def test_a_patch_that_does_not_fit_is_refused(self, patch, message):
        # Arrange
        source = SOURCE

        # Act
        with pytest.raises(pat.PatError) as raised:
            pat.apply(source, patch)

        # Assert
        assert str(raised.value) == message


class TestDetecting:
    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            (WORKED, True),
            (b"PATCH" + bytes(10), False),
            (b"just some text\r\n", False),
            (bytes(range(256)), False),
        ],
        ids=["records", "binary-magic", "plain-text", "binary"],
    )
    def test_only_text_with_a_record_line_is_pat(self, data, expected):
        # Arrange
        candidate = data

        # Act
        found = pat.matches(candidate)

        # Assert
        assert found is expected


class TestWriting:
    def test_every_differing_byte_becomes_a_record(self):
        # Arrange
        after = b"AbCDEFGHIJkL"

        # Act
        patch = pat.build(SOURCE, after)

        # Assert
        assert patch == (
            b"Comparing files source and target\r\n00000001: 42 62\r\n0000000A: 4B 6B\r\n"
        )

    def test_a_size_change_is_refused(self):
        # Arrange
        after = SOURCE + b"!"

        # Act
        with pytest.raises(pat.PatError) as raised:
            pat.build(SOURCE, after)

        # Assert
        assert str(raised.value) == "PAT holds only byte changes, so it cannot change a file's size"

    def test_an_offset_past_four_gibibytes_cannot_be_written(self):
        # Arrange
        offset = 1 << 32

        # Act
        with pytest.raises(pat.PatError) as raised:
            pat.record(offset, 0, 1)

        # Assert
        assert (
            str(raised.value) == "PAT offsets have 8 hex digits, so 0x100000000 cannot be written"
        )


class TestIdenticalFiles:
    def test_one_record_rewrites_the_first_byte_so_the_patch_still_reads(self):
        # Arrange
        before = b"same"

        # Act
        patch = pat.build(before, before)

        # Assert
        assert patch.endswith(b"\r\n00000000: 73 73\r\n")
        assert pat.apply(before, patch) == before

    def test_two_empty_files_are_refused(self):
        # Arrange
        before = b""

        # Act
        with pytest.raises(pat.PatError) as raised:
            pat.build(before, before)

        # Assert
        assert str(raised.value) == "two empty files leave PAT nothing to record"
