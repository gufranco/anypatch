import pytest

from anypatch.formats import vpatch
from anypatch.formats import vpatch_vectors_test_support as vectors

CASES = {case.name: case for case in vectors.cases()}


class TestTheReferencePairs:
    def test_every_case_has_a_patch_written_by_genpat(self):
        # Arrange
        names = set(CASES)

        # Act
        recorded = set(vectors.PATCHES)

        # Assert
        assert recorded == names

    def test_the_cases_regenerate_the_same_bytes(self):
        # Arrange
        first = {case.name: (case.source, case.target) for case in vectors.cases()}

        # Act
        second = {case.name: (case.source, case.target) for case in vectors.cases()}

        # Assert
        assert first == second


class TestTheReferencePatches:
    @pytest.mark.parametrize("name", sorted(CASES))
    def test_a_patch_genpat_wrote_rebuilds_its_target(self, name):
        # Arrange
        case = CASES[name]

        # Act
        result = vpatch.apply(case.source, vectors.PATCHES[name])

        # Assert
        assert result == case.target

    def test_a_crc32_mode_patch_genpat_appended_rebuilds_its_target(self):
        # Arrange
        case = CASES["edit"]

        # Act
        result = vpatch.apply(case.source, vectors.CRC_EDIT)

        # Assert
        assert result == case.target

    @pytest.mark.parametrize("name", ["edit", "moved"])
    def test_each_source_finds_its_own_entry_in_a_two_entry_file(self, name):
        # Arrange
        case = CASES[name]

        # Act
        result = vpatch.apply(case.source, vectors.EDIT_AND_MOVED)

        # Assert
        assert result == case.target

    def test_the_sample_patch_shipped_with_nsis_rebuilds_its_new_file(self):
        # Arrange
        source = vectors.NSIS_OLDFILE

        # Act
        result = vpatch.apply(source, vectors.NSIS_PATCH)

        # Assert
        assert result == vectors.NSIS_NEWFILE
