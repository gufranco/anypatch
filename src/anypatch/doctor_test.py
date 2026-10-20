import pytest

from anypatch import doctor
from anypatch.version import VERSION


def importer_without(*missing: str):
    def load(name: str) -> object:
        if name in missing:
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return object()

    return load


def by_name(report: doctor.DoctorReport) -> dict[str, doctor.Check]:
    return {check.name: check for check in report.checks}


class TestTheReport:
    def test_a_complete_python_is_healthy_and_names_every_check(self):
        # Arrange
        importer = importer_without()

        # Act
        report = doctor.diagnose(importer=importer, python=(3, 14, 0))

        # Assert
        checks = by_name(report)
        assert report.healthy is True
        assert list(checks) == ["anypatch", "python", "platform", "zlib", "bz2", "lzma"]
        assert checks["anypatch"].detail == VERSION
        assert checks["python"].detail == "3.14.0"
        assert {check.status for check in report.checks} == {doctor.CheckStatus.OK}

    def test_a_missing_codec_is_reported_without_failing_the_install(self):
        # Arrange
        importer = importer_without("lzma")

        # Act
        report = doctor.diagnose(importer=importer, python=(3, 14, 0))

        # Assert
        lzma = by_name(report)["lzma"]
        assert lzma.status is doctor.CheckStatus.MISSING
        assert (
            lzma.detail == "this Python was built without lzma, so formats that use it are not read"
        )
        assert report.healthy is True

    def test_a_python_older_than_the_floor_fails(self):
        # Arrange
        importer = importer_without()

        # Act
        report = doctor.diagnose(importer=importer, python=(3, 10, 9))

        # Assert
        python = by_name(report)["python"]
        assert python.status is doctor.CheckStatus.FAILED
        assert python.detail == "3.10.9, older than 3.11, the oldest supported"
        assert report.healthy is False

    def test_an_empty_report_has_no_verdict(self):
        # Arrange
        report = doctor.DoctorReport(())

        # Act
        with pytest.raises(ValueError) as raised:
            _ = report.healthy

        # Assert
        assert str(raised.value) == "nothing was checked, so there is no verdict to give"

    def test_the_running_python_is_checked_when_none_is_given(self):
        # Arrange
        importer = importer_without()

        # Act
        report = doctor.diagnose(importer=importer)

        # Assert
        assert by_name(report)["python"].status is doctor.CheckStatus.OK
