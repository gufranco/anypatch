import hashlib

import pytest

from anypatch.formats import dldi
from anypatch.formats import dldi_vectors_test_support as vectors

CASES = {case.name: case for case in vectors.cases()}


class TestTheReferenceCases:
    def test_every_case_has_a_result_written_by_dlditool(self):
        # Arrange
        names = set(CASES)

        # Act
        recorded = set(vectors.RESULTS)

        # Assert
        assert recorded == names

    def test_the_cases_regenerate_the_same_bytes(self):
        # Arrange
        first = {case.name: (case.app, case.driver) for case in vectors.cases()}

        # Act
        second = {case.name: (case.app, case.driver) for case in vectors.cases()}

        # Assert
        assert first == second


class TestTheReferenceResults:
    @pytest.mark.parametrize("name", sorted(CASES))
    def test_the_driver_lands_as_dlditool_patches_it(self, name):
        # Arrange
        case = CASES[name]

        # Act
        result = dldi.apply(case.app, case.driver)

        # Assert
        assert hashlib.sha256(result).hexdigest() == vectors.RESULTS[name]
