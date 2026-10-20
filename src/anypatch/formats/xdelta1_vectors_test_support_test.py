import pytest

from anypatch.formats import xdelta1
from anypatch.formats import xdelta1_vectors_test_support as vectors

CASES = {case.name: case for case in vectors.cases()}
RECORDED = sorted(vectors.PATCHES)


class TestTheReferencePairs:
    def test_every_case_has_a_patch_from_xdelta1_in_every_mode(self):
        # Arrange
        expected = {f"{name}/{mode}" for name in CASES for mode in vectors.MODES}

        # Act
        recorded = set(vectors.PATCHES)

        # Assert
        assert recorded == expected

    def test_the_cases_regenerate_the_same_bytes(self):
        # Arrange
        first = {case.name: (case.source, case.target) for case in vectors.cases()}

        # Act
        second = {case.name: (case.source, case.target) for case in vectors.cases()}

        # Assert
        assert first == second


class TestTheReferencePatches:
    @pytest.mark.parametrize("key", RECORDED)
    def test_a_patch_xdelta1_wrote_rebuilds_its_target(self, key):
        # Arrange
        case = CASES[key.split("/")[0]]

        # Act
        result = xdelta1.apply(case.source, vectors.PATCHES[key])

        # Assert
        assert result == case.target
