import pytest

from anypatch.formats import hdiff
from anypatch.formats import hdiff_vectors_test_support as vectors

CASES = {case.name: case for case in vectors.cases()}
KEYS = sorted(vectors.PATCHES)


class TestTheReferencePairs:
    def test_every_case_has_a_patch_for_every_mode(self):
        # Arrange
        expected = {(name, mode) for name in CASES for mode in vectors.MODES}

        # Act
        recorded = set(vectors.PATCHES)

        # Assert
        assert recorded == expected


class TestThePatchesHdiffzWrote:
    @pytest.mark.parametrize(("name", "mode"), KEYS, ids=[f"{n}-{m}" for n, m in KEYS])
    def test_each_rebuilds_its_target(self, name, mode):
        # Arrange
        case = CASES[name]

        # Act
        result = hdiff.apply(case.source, vectors.PATCHES[name, mode])

        # Assert
        assert result == case.target
