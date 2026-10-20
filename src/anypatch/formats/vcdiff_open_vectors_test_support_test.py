import pytest

from anypatch.formats import vcdiff
from anypatch.formats import vcdiff_open_vectors_test_support as vectors

CASES = {case.name: case for case in vectors.cases()}
KEYS = sorted(vectors.PATCHES)


class TestTheReferencePairs:
    def test_every_case_has_a_patch_for_every_flag_set(self):
        # Arrange
        expected = {(name, flags) for name in CASES for flags in vectors.FLAGS}

        # Act
        recorded = set(vectors.PATCHES)

        # Assert
        assert recorded == expected


class TestThePatchesOpenVcdiffWrote:
    @pytest.mark.parametrize(("name", "flags"), KEYS, ids=[f"{n}-{f}" for n, f in KEYS])
    def test_each_rebuilds_its_target(self, name, flags):
        # Arrange
        case = CASES[name]

        # Act
        result = vcdiff.apply(case.source, vectors.PATCHES[name, flags])

        # Assert
        assert result == case.target
