import hashlib
import zlib

import pytest

from anypatch import boundaries_test_support as boundaries

CASES = {case.name: case for case in boundaries.cases()}


class TestSeededContent:
    def test_the_same_seed_gives_the_same_bytes(self):
        # Arrange
        first = boundaries.seeded(7, 1000)

        # Act
        second = boundaries.seeded(7, 1000)

        # Assert
        assert first == second

    def test_a_flipped_range_differs_at_every_byte(self):
        # Arrange
        image = bytes(64)

        # Act
        result = boundaries.flipped(image, 3, [(10, 20)])

        # Assert
        assert all(byte != 0 for byte in result[10:30])
        assert result[:10] + result[30:] == bytes(44)

    def test_a_fill_past_the_end_appends_its_marker_value(self):
        # Arrange
        image = b"abc"

        # Act
        result = boundaries.filled(image, 3, 2)

        # Assert
        assert result == b"abc\xa5\xa5"


class TestForgedChecksums:
    @pytest.mark.parametrize("crc", [0, 0xFFFFFFFF, 0xA7F5CD7E, 0x12345678])
    def test_the_last_four_bytes_set_any_crc32(self, crc):
        # Arrange
        image = boundaries.seeded(5, 4096)

        # Act
        forged = boundaries.with_crc(image, crc)

        # Assert
        assert zlib.crc32(forged) == crc
        assert forged[:-4] == image[:-4]


class TestTheCatalogue:
    def test_every_case_has_a_unique_name(self):
        # Arrange
        names = [case.name for case in boundaries.cases()]

        # Act
        unique = set(names)

        # Assert
        assert len(unique) == len(names)

    @pytest.mark.parametrize("name", sorted(CASES))
    def test_each_case_holds_the_recorded_bytes(self, name):
        # Arrange
        case = CASES[name]

        # Act
        digest = hashlib.sha256(case.source + b"|" + case.target).hexdigest()[:16]

        # Assert
        assert (len(case.source), len(case.target), digest) == boundaries.RECORDED[name]
