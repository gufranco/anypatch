from __future__ import annotations

import json
from typing import Annotated

import typer

from anypatch import doctor
from anypatch.version import VERSION

NAME_WIDTH = 12
DOCTOR_HELP = "Check the installation: version, Python, platform and the codecs formats need."

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Read, write, merge and convert binary patches.",
)


def doctor_lines(report: doctor.DoctorReport) -> list[str]:
    return [
        f"{check.name:<{NAME_WIDTH}} {check.detail}"
        + ("" if check.status is doctor.CheckStatus.OK else f" [{check.status}]")
        for check in report.checks
    ]


def doctor_json(report: doctor.DoctorReport) -> str:
    checks = [
        {"name": check.name, "status": str(check.status), "detail": check.detail}
        for check in report.checks
    ]
    return json.dumps({"healthy": report.healthy, "checks": checks}, indent=2)


def exit_code(report: doctor.DoctorReport) -> int:
    return 0 if report.healthy else 1


def _version(value: bool) -> None:
    if value:
        typer.echo(f"anypatch {VERSION}")
        raise typer.Exit(code=0)


@app.callback()
def main(
    *,
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version, is_eager=True, help="print the version"),
    ] = False,
) -> None:
    del version


@app.command("doctor", help=DOCTOR_HELP)
def doctor_command(
    *,
    json_output: Annotated[bool, typer.Option("--json", help="print the report as JSON")] = False,
) -> None:
    report = doctor.diagnose()
    typer.echo(doctor_json(report) if json_output else "\n".join(doctor_lines(report)))
    raise typer.Exit(code=exit_code(report))
