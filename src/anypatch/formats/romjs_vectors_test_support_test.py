import pytest

from n64_save_patches import patchio
from n64_save_patches import romjs_vectors_test_support as vectors

CASES = {case.name: case for case in vectors.cases()}


class TestTheReferencePairs:
    def test_every_case_regenerates_the_same_bytes(self):
        # Arrange
        first = {case.name: (case.source, case.target) for case in vectors.cases()}

        # Act
        second = {case.name: (case.source, case.target) for case in vectors.cases()}

        # Assert
        assert first == second

    def test_every_case_and_format_has_a_recorded_patch(self):
        # Arrange
        wanted = set(vectors.names())

        # Act
        recorded = set(vectors.PATCHES)

        # Assert
        assert recorded == wanted

    def test_every_source_starts_like_an_n64_dump(self):
        # Arrange
        sources = [case.source for case in vectors.cases()]

        # Act
        starts = {source[:4] for source in sources}

        # Assert
        assert starts == {b"\x80\x37\x12\x40"}


class TestTheReferencePatches:
    @pytest.mark.parametrize("name", vectors.names())
    def test_a_patch_written_by_the_reference_turns_the_source_into_the_target(
        self, name, tmp_path
    ):
        # Arrange
        case = CASES[name.split(".")[0]]
        path = tmp_path / name
        path.write_bytes(vectors.PATCHES[name])

        # Act
        replayed = patchio.apply(case.source, patchio.read(path))

        # Assert
        assert replayed == case.target
