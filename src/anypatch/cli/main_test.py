import json

from typer.testing import CliRunner

from anypatch import doctor
from anypatch.cli.main import app, doctor_lines, exit_code
from anypatch.patchio import Format
from anypatch.version import VERSION

RUNNER = CliRunner()


class TestTheVersion:
    def test_it_prints_the_name_and_version(self):
        # Arrange
        args = ["--version"]

        # Act
        result = RUNNER.invoke(app, args)

        # Assert
        assert result.exit_code == 0
        assert result.output == f"anypatch {VERSION}\n"


class TestDoctor:
    def test_it_prints_one_line_per_check_and_exits_zero_when_healthy(self):
        # Arrange
        args = ["doctor"]

        # Act
        result = RUNNER.invoke(app, args)

        # Assert
        lines = result.output.splitlines()
        assert result.exit_code == 0
        assert lines[0] == f"anypatch     {VERSION}"
        assert [line.split()[0] for line in lines] == [
            "anypatch",
            "python",
            "platform",
            "zlib",
            "bz2",
            "lzma",
            *(kind.value for kind in Format),
        ]

    def test_json_carries_the_verdict_and_every_check(self):
        # Arrange
        args = ["doctor", "--json"]

        # Act
        result = RUNNER.invoke(app, args)

        # Assert
        report = json.loads(result.output)
        assert result.exit_code == 0
        assert report["healthy"] is True
        assert report["checks"][0] == {"name": "anypatch", "status": "ok", "detail": VERSION}

    def test_a_check_that_is_not_ok_carries_its_status(self):
        # Arrange
        report = doctor.DoctorReport(
            (
                doctor.Check("python", doctor.CheckStatus.FAILED, "3.10.9"),
                doctor.Check("lzma", doctor.CheckStatus.MISSING, "absent"),
            )
        )

        # Act
        lines = doctor_lines(report)

        # Assert
        assert lines == ["python       3.10.9 [failed]", "lzma         absent [missing]"]

    def test_a_failed_check_makes_the_exit_code_one(self):
        # Arrange
        report = doctor.DoctorReport((doctor.Check("python", doctor.CheckStatus.FAILED, "x"),))

        # Act
        code = exit_code(report)

        # Assert
        assert code == 1

    def test_with_no_command_it_shows_the_help(self):
        # Arrange
        args: list[str] = []

        # Act
        result = RUNNER.invoke(app, args)

        # Assert
        assert "doctor" in result.output
