import pytest

from anypatch.formats import bsp
from anypatch.formats import bsp_vectors_test_support as vectors


class TestTheReferencePrograms:
    def test_every_program_has_a_compiled_patch_and_a_reference_result(self):
        # Arrange
        names = set(vectors.SOURCES)

        # Act
        recorded = (set(vectors.PATCHES), set(vectors.RESULTS))

        # Assert
        assert recorded == (names, names)

    @pytest.mark.parametrize("name", sorted(vectors.SOURCES))
    def test_a_program_bspcomp_compiled_gives_what_bsppatch_js_gives(self, name):
        # Arrange
        choices = vectors.CHOICES.get(name, ())

        # Act
        result = bsp.apply(vectors.INPUT, vectors.PATCHES[name], choices=choices)

        # Assert
        assert result == vectors.RESULTS[name]
