from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from anypatch import api, patchio
from anypatch.conflicts import ConflictError, Merged
from anypatch.patchio import Format, Patch, PatchError

HEADER_SUFFIX = patchio.HEADER_SUFFIX
LABEL_WIDTH = 15

Output = Annotated[Path, typer.Option("-o", "--output", help="where the result goes")]
FormatOption = Annotated[
    Format | None,
    typer.Option("--format", help="the patch format; by default the output's extension decides"),
]
Description = Annotated[
    str, typer.Option("--description", help="the text an APS, BPS, EBP, PPF or RUP patch carries")
]
Clean = Annotated[
    Path | None,
    typer.Option("--clean", help="the clean source, when the input already carries a patch"),
]
Json = Annotated[bool, typer.Option("--json", help="print the answer as JSON")]
Choices = Annotated[
    list[int] | None,
    typer.Option("--choice", help="the option a BSP menu takes; repeat it for each menu in turn"),
]


class RefusedError(Exception):
    pass


def _label(name: str, value: str) -> str:
    return f"{name:<{LABEL_WIDTH}}{value}"


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise RefusedError(f"cannot read {path}: {error.strerror or error}") from error


def _patches(paths: list[Path], choices: list[int] | None = None) -> list[Patch]:
    for path in paths:
        _read(path)
    taken = tuple(choices or ())
    return [dataclasses.replace(patchio.read(path), choices=taken) for path in paths]


def _kind(target: Path, chosen: Format | None) -> Format:
    return chosen if chosen is not None else patchio.format_of(target)


def _planned(target: Path, encoded: dict[str, bytes]) -> dict[Path, bytes]:
    return {
        (target.with_suffix(HEADER_SUFFIX) if suffix == HEADER_SUFFIX else target): data
        for suffix, data in encoded.items()
    }


def _write(planned: dict[Path, bytes]) -> None:
    for path, data in planned.items():
        path.write_bytes(data)
        typer.echo(_label("wrote", f"{path}, {len(data):,} bytes"))


def _report(merged: Merged) -> None:
    typer.echo(_label("applied", ", ".join(merged.applied) or "nothing new"))
    if merged.already:
        typer.echo(_label("already in", ", ".join(merged.already)))


def _guarded(work: Callable[[], None]) -> None:
    try:
        work()
    except (RefusedError, PatchError, ConflictError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error


def make_command(
    before: Path,
    after: Path,
    output: Output,
    *,
    kind: FormatOption = None,
    description: Description = "",
) -> None:
    def work() -> None:
        chosen = _kind(output, kind)
        encoded = api.make(_read(before), _read(after), chosen, description=description)
        _write(_planned(output, encoded))

    _guarded(work)


def apply_command(
    source: Path,
    patch: list[Path],
    output: Output,
    *,
    clean: Clean = None,
    choice: Choices = None,
) -> None:
    def work() -> None:
        base = _read(clean) if clean is not None else None
        merged = api.apply(_read(source), _patches(patch, choice), clean=base)
        _report(merged)
        _write({output: merged.image})

    _guarded(work)


def merge_command(
    source: Path,
    patch: list[Path],
    output: Output,
    *,
    kind: FormatOption = None,
    clean: Clean = None,
    description: Description = "",
) -> None:
    def work() -> None:
        chosen = _kind(output, kind)
        base = _read(clean) if clean is not None else None
        patches = _patches(patch)
        encoded = api.merge(_read(source), patches, chosen, clean=base, description=description)
        _write(_planned(output, encoded))

    _guarded(work)


def convert_command(
    source: Path,
    patch: Path,
    output: Output,
    *,
    kind: FormatOption = None,
    description: Description = "",
) -> None:
    def work() -> None:
        chosen = _kind(output, kind)
        encoded = api.convert(_read(source), _patches([patch])[0], chosen, description=description)
        _write(_planned(output, encoded))

    _guarded(work)


def info_command(patch: Path, *, json_output: Json = False) -> None:
    def work() -> None:
        data = _read(patch)
        entry = {one.format: one for one in api.formats()}[api.identify(data, name=patch.name)]
        if json_output:
            shown = {"format": entry.format.value, "name": entry.name}
            typer.echo(json.dumps({**shown, "binding": entry.binding, "size": len(data)}, indent=2))
            return
        typer.echo(_label("format", entry.name))
        typer.echo(_label("bound by", entry.binding))
        typer.echo(_label("size", f"{len(data):,} bytes"))

    _guarded(work)


def formats_command(*, json_output: Json = False) -> None:
    listed = api.formats()
    if json_output:
        rows = [
            {
                "format": one.format.value,
                "name": one.name,
                "extensions": list(one.extensions),
                "reads": one.reads,
                "writes": one.writes,
                "binding": one.binding,
            }
            for one in listed
        ]
        typer.echo(json.dumps(rows, indent=2))
        return
    for one in listed:
        support = "read and write" if one.writes else "read only"
        typer.echo(f"{one.name:<13}{support:<16}{' '.join(one.extensions):<34}{one.binding}")


COMMANDS = (
    ("make", make_command, "Write the patch that turns one file into another."),
    (
        "apply",
        apply_command,
        "Apply patches together, refusing any conflict, and write the result.",
    ),
    ("merge", merge_command, "Merge patches made for one source into a single patch."),
    ("convert", convert_command, "Rewrite a patch in another format."),
    ("info", info_command, "Name a patch's format and what binds it to its source."),
    (
        "formats",
        formats_command,
        "List every format, what is read and written, and the extensions.",
    ),
)


def register(app: typer.Typer) -> None:
    for name, command, text in COMMANDS:
        app.command(name, help=text)(command)
