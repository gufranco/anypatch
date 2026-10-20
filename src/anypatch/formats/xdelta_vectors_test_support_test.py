from anypatch.formats import xdelta_vectors_test_support as vectors


class TestTheReferencePairs:
    def test_every_case_regenerates_the_same_bytes(self):
        # Arrange
        first = {case.name: (case.source, case.target) for case in vectors.cases()}

        # Act
        second = {case.name: (case.source, case.target) for case in vectors.cases()}

        # Assert
        assert first == second

    def test_every_case_has_a_patch_written_by_xdelta3(self):
        # Arrange
        names = {case.name for case in vectors.cases()}

        # Act
        recorded = set(vectors.PATCHES)

        # Assert
        assert recorded == names

    def test_the_noise_generator_is_pinned(self):
        # Arrange
        seed = 1

        # Act
        start = vectors.noise(8, seed)

        # Assert
        assert start == vectors.noise(16, seed)[:8]
        assert len(set(vectors.noise(4096, seed))) > 200
