import pytest

from anypatch.formats import jojodiff
from anypatch.formats import jojodiff_vectors_test_support as vectors

CASES = {case.name: case for case in vectors.cases()}


class TestTheReferencePairs:
    def test_every_case_has_a_patch_written_by_jdiff(self):
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
    def test_a_patch_jdiff_wrote_rebuilds_its_target(self, name):
        # Arrange
        case = CASES[name]

        # Act
        result = jojodiff.apply(case.source, vectors.PATCHES[name])

        # Assert
        assert result == case.target
