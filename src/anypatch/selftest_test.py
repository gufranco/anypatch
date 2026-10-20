from anypatch import selftest
from anypatch.doctor import CheckStatus
from anypatch.patchio import WRITABLE, Format, PatchError


class TestEveryFormat:
    def test_each_format_passes_its_own_check(self):
        # Arrange
        expected = [kind.value for kind in Format]

        # Act
        checks = selftest.run()

        # Assert
        assert [check.name for check in checks] == expected
        assert {check.status for check in checks} == {CheckStatus.OK}

    def test_a_writable_format_says_it_reads_and_writes(self):
        # Arrange
        kind = WRITABLE[0]

        # Act
        check = selftest.check(kind)

        # Assert
        assert check.detail == "reads and writes"

    def test_star_rod_is_checked_by_decoding_a_patch(self):
        # Arrange
        kind = Format.PMSR

        # Act
        check = selftest.check(kind)

        # Assert
        assert check.detail == "reads and writes"


class TestFailures:
    def test_a_probe_whose_result_differs_fails(self):
        # Arrange
        def wrong(kind: Format) -> bool:
            return False

        # Act
        check = selftest.check(Format.IPS, probe=wrong)

        # Assert
        assert check.status is CheckStatus.FAILED
        assert check.detail == "a patch it wrote did not replay to its target"

    def test_a_probe_that_raises_fails_with_the_reason(self):
        # Arrange
        def broken(kind: Format) -> bool:
            raise PatchError("ips: damaged")

        # Act
        check = selftest.check(Format.IPS, probe=broken)

        # Assert
        assert check.status is CheckStatus.FAILED
        assert check.detail == "ips: damaged"
