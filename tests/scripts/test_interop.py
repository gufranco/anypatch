from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "interop.py"
MAKER = '#!/bin/sh\nexec "{python}" -m anypatch make "$1" "$2" -o "$3" --format bdf\n'
PATCHER = '#!/bin/sh\nexec "{python}" -m anypatch apply "$1" "$3" -o "$2"\n'
BROKEN = "#!/bin/sh\necho refused >&2\nexit 3\n"


def tools(folder: Path, maker: str, patcher: str) -> Path:
    folder.mkdir()
    for name, body in (("bsdiff", maker), ("bspatch", patcher)):
        (folder / name).write_text(body.format(python=sys.executable))
        (folder / name).chmod(0o755)
    return folder


def run(bin_folder: Path, work: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "PATH": f"{bin_folder}{os.pathsep}{os.environ['PATH']}",
        "PYTHONPATH": str(ROOT / "src"),
    }
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--tool", "bsdiff", "--work", str(work), *extra],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )


class TestAToolThatAgrees:
    def test_both_directions_pass_and_the_exit_code_is_zero(self, tmp_path):
        # Arrange
        folder = tools(tmp_path / "bin", MAKER, PATCHER)

        # Act
        done = run(folder, tmp_path / "work", "--case", "first-byte")

        # Assert
        assert done.returncode == 0, done.stdout + done.stderr
        assert done.stdout.splitlines() == [
            "PASS first-byte bsdiff bdf ours ",
            "PASS first-byte bsdiff bdf theirs ",
            "2 passed, 0 refused as declared, 0 known tool limits, 0 failed",
        ]


class TestAToolThatFails:
    def test_each_direction_reports_the_command_and_the_exit_code_is_one(self, tmp_path):
        # Arrange
        folder = tools(tmp_path / "bin", BROKEN, BROKEN)

        # Act
        done = run(folder, tmp_path / "work", "--case", "first-byte")

        # Assert
        assert done.returncode == 1
        assert done.stdout.count("FAIL first-byte bsdiff bdf") == 2
        assert "exit 3:" in done.stdout
        assert "refused" in done.stdout
        assert done.stdout.splitlines()[-1] == (
            "0 passed, 0 refused as declared, 0 known tool limits, 2 failed"
        )


class TestNothingSelected:
    def test_an_unknown_case_runs_nothing_and_passes(self, tmp_path):
        # Arrange
        folder = tools(tmp_path / "bin", MAKER, PATCHER)

        # Act
        done = run(folder, tmp_path / "work", "--case", "no-such-case")

        # Assert
        assert done.returncode == 1
        assert done.stdout.splitlines() == ["nothing matched the --tool and --case filters"]


def module():
    spec = importlib.util.spec_from_file_location("interop", SCRIPT)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules["interop"] = loaded
    spec.loader.exec_module(loaded)
    return loaded


INTEROP = module()
KNOWN_KEY = next(iter(INTEROP.KNOWN))


def outcome(
    *, case="first-byte", tool="bsdiff", kind=None, direction="ours", detail="", refused=""
):
    chosen = kind or INTEROP.Format.BDF
    return INTEROP.Outcome(case, tool, chosen, direction, detail, refused)


class TestVerdicts:
    def test_an_exchange_that_rebuilt_the_target_passes(self):
        # Arrange
        one = outcome()

        # Act
        found = INTEROP.verdict(one)

        # Assert
        assert found == (INTEROP.Mark.PASS, "")

    def test_an_undeclared_failure_fails_with_its_detail(self):
        # Arrange
        one = outcome(detail="exit 1: bspatch")

        # Act
        found = INTEROP.verdict(one)

        # Assert
        assert found == (INTEROP.Mark.FAIL, "exit 1: bspatch")

    def test_a_declared_tool_limit_that_fails_is_known(self):
        # Arrange
        tool, kind, direction, case = KNOWN_KEY
        one = outcome(case=case, tool=tool, kind=kind, direction=direction, detail="exit 1")

        # Act
        found = INTEROP.verdict(one)

        # Assert
        assert found == (INTEROP.Mark.KNOWN, INTEROP.KNOWN[KNOWN_KEY])

    def test_a_declared_tool_limit_that_now_passes_fails_so_the_table_is_corrected(self):
        # Arrange
        tool, kind, direction, case = KNOWN_KEY
        one = outcome(case=case, tool=tool, kind=kind, direction=direction)

        # Act
        found = INTEROP.verdict(one)

        # Assert
        assert found == (
            INTEROP.Mark.FAIL,
            f"the declared limit no longer reproduces: {INTEROP.KNOWN[KNOWN_KEY]}",
        )

    def test_a_declared_refusal_that_happened_is_reported_as_refused(self):
        # Arrange
        one = outcome(refused="cannot shrink")

        # Act
        found = INTEROP.verdict(one)

        # Assert
        assert found == (INTEROP.Mark.REFUSED, "cannot shrink")

    def test_a_declared_refusal_that_went_wrong_fails(self):
        # Arrange
        one = outcome(refused="cannot shrink", detail="anypatch wrote a patch it should refuse")

        # Act
        found = INTEROP.verdict(one)

        # Assert
        assert found == (INTEROP.Mark.FAIL, "anypatch wrote a patch it should refuse")


class TestARefusalOnOurSide:
    def test_the_tool_is_never_run_and_the_refusal_is_checked(self, tmp_path):
        # Arrange
        case = next(one for one in INTEROP.boundaries.cases() if one.name == "shrink-by-one")
        exchange = INTEROP.Exchange("never", INTEROP.Format.PPF, None, "false")

        # Act
        found = INTEROP.attempt(case, exchange, INTEROP.OURS, tmp_path)

        # Assert
        assert (found.detail, found.refused) == ("", "cannot shrink")

    def test_a_patch_written_where_a_refusal_was_declared_fails(self, tmp_path):
        # Arrange
        case = next(one for one in INTEROP.boundaries.cases() if one.name == "first-byte")
        exchange = INTEROP.Exchange("never", INTEROP.Format.PPF, None, "false")

        # Act
        found = INTEROP.check_refusal(case, exchange, "cannot shrink")

        # Assert
        assert found == "anypatch wrote a ppf patch where it should refuse: cannot shrink"

    def test_a_different_refusal_than_declared_fails_with_both_texts(self, tmp_path):
        # Arrange
        case = next(one for one in INTEROP.boundaries.cases() if one.name == "shrink-by-one")
        exchange = INTEROP.Exchange("never", INTEROP.Format.PPF, None, "false")

        # Act
        found = INTEROP.check_refusal(case, exchange, "some other reason")

        # Assert
        assert found.startswith("expected a refusal naming 'some other reason', got ")
