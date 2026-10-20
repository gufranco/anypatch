import importlib

import pytest

from anypatch import entry
from anypatch.version import VERSION


def missing(name: str):
    def load(module: str) -> object:
        raise ModuleNotFoundError(f"No module named {name!r}", name=name)

    return load


class TestTheEntryPoint:
    def test_it_runs_the_command_line(self, capsys):
        # Arrange
        argv = ["--version"]

        # Act
        with pytest.raises(SystemExit) as raised:
            entry.main(argv, importer=importlib.import_module)

        # Assert
        assert raised.value.code == 0
        assert capsys.readouterr().out == f"anypatch {VERSION}\n"

    def test_without_the_cli_extra_it_says_how_to_get_it(self, capsys):
        # Arrange
        importer = missing("typer")

        # Act
        with pytest.raises(SystemExit) as raised:
            entry.main(["doctor"], importer=importer)

        # Assert
        assert raised.value.code == 1
        assert capsys.readouterr().err == entry.MISSING_CLI + "\n"

    def test_any_other_missing_module_is_not_hidden(self):
        # Arrange
        importer = missing("anypatch.cli.main")

        # Act
        with pytest.raises(ModuleNotFoundError) as raised:
            entry.main([], importer=importer)

        # Assert
        assert raised.value.name == "anypatch.cli.main"
