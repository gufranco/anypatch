from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from anypatch import api
from anypatch import boundaries_test_support as boundaries
from anypatch.patchio import Format, PatchError

TIMEOUT = 300
LOG_TAIL = 2000
REPORT_WIDTH = 600
OURS = "ours"
THEIRS = "theirs"
ROMJS_WRITES = (Format.IPS, Format.EBP, Format.UPS, Format.BPS, Format.PPF, Format.APS, Format.RUP)
ROMJS_READS = (*ROMJS_WRITES, Format.BDF, Format.APS_GBA, Format.PMSR)
XDELTA_CODERS = ("none", "lzma", "djw", "fgk")
NOTHING = "nothing matched the --tool and --case filters"


@dataclass(frozen=True, slots=True)
class Exchange:
    tool: str
    kind: Format
    make: str | None
    apply: str | None


@dataclass(frozen=True, slots=True)
class Outcome:
    case: str
    tool: str
    kind: Format
    direction: str
    detail: str
    refused: str = ""


class Mark(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    REFUSED = "REFUSED"
    KNOWN = "KNOWN"


ROMJS_EMPTY = "RomPatcher.js cannot open an empty file: BinFile.slice throws"
ROMJS_BZ2 = (
    "RomPatcher.js loses the last bytes of a BDF diff that runs to the end of the source; "
    "it misreads bsdiff's own patch for the same files"
)
ROMJS_IPS32 = "RomPatcher.js does not read IPS32"
ROMJS_IPS_BIG = "RomPatcher.js refuses IPS and EBP past 16 MiB"
ROMJS_TRUNCATE_ZERO = "RomPatcher.js treats an IPS truncation to 0 bytes as no truncation"
ROMJS_TRUNCATE_WRAP = "RomPatcher.js writes a 16 MiB truncation into 3 bytes, where it wraps to 0"
ROMJS_NO_SHRINK = "RomPatcher.js writes PPF and EBP for a shrink, which neither can express"
ROMJS_GBA_SIZE = "RomPatcher.js reads APS for GBA only when the size stays the same"
ROMJS_GBA_PARTIAL = (
    "RomPatcher.js checks the CRC16 of a partial last APS for GBA block without its zero "
    "padding, where UniPatcher and anypatch pad it"
)
IPS32_CASES = (
    "ips-past-limit-high-change",
    "ips-shrink-to-limit",
    "pmsr-base-edit",
    "pmsr-base-grow",
    "xdelta-window-0x1000001",
)
GBA_RESIZED = (
    "data-to-empty",
    "empty-to-data",
    "grow-by-one",
    "ips-grow-to-limit",
    "pmsr-base-grow",
    "varint-0x3fff",
    "varint-0x4000",
    "varint-0x7f",
    "varint-0x80",
)
FLIPS_IPS32 = "Flips does not read IPS32"
FLIPS_IPS_BIG = "Flips refuses IPS for a file over 16 MiB, whatever the changes"
FLIPS_EOF_RUN = "Flips never finishes an IPS whose run starts at the EOF offset"
FLIPS_EMPTY_BPS = "Flips writes a BPS for an empty target that it reports as broken itself"
NINJA_ZERO = (
    "NINJA writes 0 as a zero-width number, and on PHP 8 its fread of zero bytes throws where "
    "PHP 5 returned nothing"
)
MAKEPPF_SIZE = "MakePPF compares only the length both files share, so it drops a size change"
PPF_RESIZED = (
    "data-to-empty",
    "empty-to-data",
    "grow-by-one",
    "ips-grow-to-limit",
    "ips-shrink-below-limit",
    "ips-shrink-to-limit",
    "pmsr-base-grow",
    "shrink-by-one",
    "varint-0x3fff",
    "varint-0x4000",
    "varint-0x7f",
    "varint-0x80",
)
KNOWN: Mapping[tuple[str, Format, str, str], str] = {
    **{("flips", Format.IPS, OURS, case): FLIPS_IPS32 for case in IPS32_CASES},
    **{
        ("flips", Format.IPS, THEIRS, case): FLIPS_IPS_BIG
        for case in (*IPS32_CASES, "ips-past-limit-low-change")
    },
    ("flips", Format.IPS, THEIRS, "ips-run-at-eof-offset"): FLIPS_EOF_RUN,
    ("flips", Format.BPS, THEIRS, "data-to-empty"): FLIPS_EMPTY_BPS,
    ("ninja", Format.RUP, THEIRS, "identical"): "NINJA deletes the patch for identical files",
    **{
        ("ninja", Format.RUP, direction, case): NINJA_ZERO
        for direction, case in (
            (OURS, "empty-to-data"),
            (OURS, "data-to-empty"),
            (OURS, "first-byte"),
            (THEIRS, "empty-to-data"),
            (THEIRS, "data-to-empty"),
        )
    },
    **{
        (tool, Format.PPF, THEIRS, case): MAKEPPF_SIZE
        for tool in ("makeppf3", "makeppf3-plain")
        for case in PPF_RESIZED
    },
    ("bsdiff", Format.BDF, THEIRS, "empty-to-data"): "bsdiff cannot mmap an empty file",
    ("bsdiff", Format.BDF, THEIRS, "data-to-empty"): "bsdiff cannot mmap an empty file",
    ("xdelta3", Format.XDELTA, OURS, "data-to-empty"): "xdelta3 refuses to write an empty output",
    ("romjs", Format.UPS, OURS, "empty-to-data"): ROMJS_EMPTY,
    ("romjs", Format.BPS, OURS, "empty-to-data"): ROMJS_EMPTY,
    ("romjs", Format.RUP, OURS, "empty-to-data"): ROMJS_EMPTY,
    ("romjs", Format.RUP, THEIRS, "empty-to-data"): ROMJS_EMPTY,
    ("romjs", Format.RUP, THEIRS, "data-to-empty"): ROMJS_EMPTY,
    ("romjs", Format.IPS, OURS, "data-to-empty"): ROMJS_TRUNCATE_ZERO,
    ("romjs", Format.IPS, THEIRS, "data-to-empty"): ROMJS_TRUNCATE_ZERO,
    ("romjs", Format.IPS, THEIRS, "ips-shrink-to-limit"): ROMJS_TRUNCATE_WRAP,
    ("romjs", Format.EBP, THEIRS, "data-to-empty"): ROMJS_NO_SHRINK,
    **{
        ("romjs", Format.PPF, THEIRS, case): ROMJS_NO_SHRINK
        for case in (
            "data-to-empty",
            "shrink-by-one",
            "ips-shrink-below-limit",
            "ips-shrink-to-limit",
        )
    },
    **{("romjs", Format.IPS, OURS, case): ROMJS_IPS32 for case in IPS32_CASES},
    **{
        ("romjs", kind, THEIRS, case): ROMJS_IPS_BIG
        for kind in (Format.IPS, Format.EBP)
        for case in IPS32_CASES
        if case != "ips-shrink-to-limit"
    },
    ("romjs", Format.EBP, THEIRS, "ips-shrink-to-limit"): ROMJS_NO_SHRINK,
    **{("romjs", Format.APS_GBA, OURS, case): ROMJS_GBA_SIZE for case in GBA_RESIZED},
    **{
        ("romjs", Format.APS_GBA, OURS, case): ROMJS_GBA_PARTIAL
        for case in ("xdelta-window-0x7fffff", "xdelta-window-0x800001", "xdelta-window-0x1000001")
    },
    **{
        ("romjs", Format.BDF, OURS, case): ROMJS_BZ2
        for case in (
            "ips-grow-to-limit",
            "ips-shrink-below-limit",
            "shrink-by-one",
            "varint-0x3fff",
            "xdelta-window-0x7fffff",
        )
    },
}


def verdict(outcome: Outcome) -> tuple[Mark, str]:
    if outcome.refused:
        return (Mark.FAIL, outcome.detail) if outcome.detail else (Mark.REFUSED, outcome.refused)
    reason = KNOWN.get((outcome.tool, outcome.kind, outcome.direction, outcome.case))
    if reason is None:
        return (Mark.FAIL, outcome.detail) if outcome.detail else (Mark.PASS, "")
    if outcome.detail:
        return Mark.KNOWN, reason
    return Mark.FAIL, f"the declared limit no longer reproduces: {reason}"


def _romjs() -> list[Exchange]:
    create = "node $ROMJS_HARNESS create {source} {target} %s {patch}"
    return [
        Exchange(
            "romjs",
            kind,
            create % kind.value if kind in ROMJS_WRITES else None,
            "node $ROMJS_HARNESS apply {source} {patch} {out}",
        )
        for kind in ROMJS_READS
    ]


def _xdelta() -> list[Exchange]:
    reader = Exchange("xdelta3", Format.XDELTA, None, "xdelta3 -d -f -s {source} {patch} {out}")
    writers = [
        Exchange(
            f"xdelta3-{coder}",
            Format.XDELTA,
            f"xdelta3 -e -f -S {coder} -s {{source}} {{target}} {{patch}}",
            None,
        )
        for coder in XDELTA_CODERS
    ]
    return [reader, *writers]


def _flips() -> list[Exchange]:
    create = "flips --create --exact --%s {source} {target} {patch}"
    apply = "flips --apply --exact {patch} {source} {out}"
    return [
        Exchange("flips", Format.IPS, create % "ips", apply),
        Exchange("flips", Format.BPS, create % "bps-delta", apply),
        Exchange("flips-linear", Format.BPS, create % "bps-linear", None),
        Exchange("flips", Format.UPS, None, apply),
    ]


def _ppf() -> list[Exchange]:
    return [
        Exchange("makeppf3", Format.PPF, "makeppf3 c -u {source} {target} {patch}", None),
        Exchange("makeppf3-plain", Format.PPF, "makeppf3 c {source} {target} {patch}", None),
        Exchange("applyppf3", Format.PPF, None, "cp {source} {out} && applyppf3 a {out} {patch}"),
    ]


def exchanges() -> list[Exchange]:
    return [
        *_romjs(),
        *_xdelta(),
        Exchange(
            "bsdiff",
            Format.BDF,
            "bsdiff {source} {target} {patch}",
            "bspatch {source} {out} {patch}",
        ),
        *_flips(),
        *_ppf(),
        Exchange(
            "ninja",
            Format.RUP,
            "mkdir -p {patch}.a {patch}.b && cp {source} {patch}.a/f && cp {target} {patch}.b/f"
            " && $NINJA {patch}.a {patch}.b {patch} raw none",
            "cp {source} {out} && $NINJA {patch} {out}",
        ),
        Exchange(
            "bsdiff4",
            Format.BDF,
            "bsdiff4 {source} {target} {patch}",
            "bspatch4 {source} {out} {patch}",
        ),
        Exchange(
            "bsdiff43",
            Format.BSDIFF43,
            "bsdiff43 {source} {target} {patch}",
            "bspatch43 {source} {out} {patch}",
        ),
        Exchange(
            "javaxdelta",
            Format.GDIFF,
            "java -cp $JAVAXDELTA com.nothome.delta.Delta {source} {target} {patch}",
            "java -cp $JAVAXDELTA com.nothome.delta.GDiffPatcher {source} {patch} {out}",
        ),
    ]


def _tail(log: Path) -> str:
    data = log.read_bytes()
    return data[-LOG_TAIL:].decode("utf-8", errors="replace")


def _run(template: str, paths: dict[str, Path]) -> str:
    quoted = {name: shlex.quote(str(path)) for name, path in paths.items()}
    command = os.path.expandvars(template.format(**quoted))
    log = paths["out"].with_name("tool.log")
    with log.open("wb") as sink:
        try:
            done = subprocess.run(
                command,
                shell=True,
                stdin=subprocess.DEVNULL,
                stdout=sink,
                stderr=subprocess.STDOUT,
                timeout=TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return f"timed out after {TIMEOUT} s: {command} {_tail(log)}"
    if done.returncode != 0:
        return f"exit {done.returncode}: {command} {_tail(log)}".strip()
    return ""


def _ours_read_by_them(case: boundaries.Boundary, one: Exchange, paths: dict[str, Path]) -> str:
    files = api.make(case.source, case.target, one.kind)
    paths["patch"].write_bytes(files[f".{one.kind.value}"])
    failed = _run(one.apply or "", paths)
    if failed:
        return failed
    made = paths["out"].read_bytes() if paths["out"].exists() else b""
    return "" if made == case.target else "their output differs from the target"


def _theirs_read_by_us(case: boundaries.Boundary, one: Exchange, paths: dict[str, Path]) -> str:
    failed = _run(one.make or "", paths)
    if failed:
        return failed
    if not paths["patch"].exists():
        return "the tool wrote no patch"
    patch = api.load(paths["patch"].read_bytes(), name=paths["patch"].name)
    image = api.apply(case.source, [patch]).image
    return "" if image == case.target else "our output differs from the target"


def _paths(work: Path, kind: Format) -> dict[str, Path]:
    return {
        "source": work / "source.bin",
        "target": work / "target.bin",
        "patch": work / f"patch.{kind.value}",
        "out": work / "out.bin",
    }


def check_refusal(case: boundaries.Boundary, one: Exchange, expected: str) -> str:
    try:
        api.make(case.source, case.target, one.kind)
    except PatchError as error:
        found = str(error)
        return "" if expected in found else f"expected a refusal naming {expected!r}, got {found}"
    return f"anypatch wrote a {one.kind.value} patch where it should refuse: {expected}"


def attempt(case: boundaries.Boundary, one: Exchange, direction: str, work: Path) -> Outcome:
    expected = boundaries.refused(case.name, one.kind) if direction == OURS else ""
    if expected:
        detail = check_refusal(case, one, expected)
        return Outcome(case.name, one.tool, one.kind, direction, detail, expected)
    paths = _paths(work, one.kind)
    paths["out"].unlink(missing_ok=True)
    paths["patch"].unlink(missing_ok=True)
    check = _ours_read_by_them if direction == OURS else _theirs_read_by_us
    try:
        detail = check(case, one, paths)
    except ValueError as error:
        detail = f"{type(error).__name__}: {error}"
    return Outcome(case.name, one.tool, one.kind, direction, detail)


def _directions(one: Exchange) -> list[str]:
    return [name for name, template in ((OURS, one.apply), (THEIRS, one.make)) if template]


def _report(outcome: Outcome, mark: Mark, detail: str) -> str:
    line = f"{mark} {outcome.case} {outcome.tool} {outcome.kind.value} {outcome.direction} "
    return (line + detail.replace("\n", " "))[:REPORT_WIDTH]


def _summary(counts: Mapping[Mark, int]) -> str:
    return (
        f"{counts[Mark.PASS]} passed, {counts[Mark.REFUSED]} refused as declared, "
        f"{counts[Mark.KNOWN]} known tool limits, {counts[Mark.FAIL]} failed"
    )


def run(cases: Sequence[boundaries.Boundary], chosen: Sequence[Exchange], work: Path) -> int:
    counts = dict.fromkeys(Mark, 0)
    for case in cases:
        (work / "source.bin").write_bytes(case.source)
        (work / "target.bin").write_bytes(case.target)
        for one in chosen:
            for direction in _directions(one):
                outcome = attempt(case, one, direction, work)
                mark, detail = verdict(outcome)
                print(_report(outcome, mark, detail), flush=True)
                counts = {**counts, mark: counts[mark] + 1}
    print(_summary(counts))
    return counts[Mark.FAIL]


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exchange boundary patches with reference tools")
    parser.add_argument(
        "--tool",
        action="append",
        default=[],
        help="tool to run; xdelta3 also runs each xdelta3-<coder>",
    )
    parser.add_argument("--case", action="append", default=[], help="case name prefix to run")
    parser.add_argument("--work", type=Path, required=True)
    return parser.parse_args(argv)


def _matches(name: str, wanted: Sequence[str]) -> bool:
    return not wanted or any(name.startswith(prefix) for prefix in wanted)


def _tool_matches(name: str, wanted: Sequence[str]) -> bool:
    return not wanted or any(name == tool or name.startswith(f"{tool}-") for tool in wanted)


def main(argv: Sequence[str]) -> int:
    options = _arguments(argv)
    chosen = [one for one in exchanges() if _tool_matches(one.tool, options.tool)]
    cases = [case for case in boundaries.cases() if _matches(case.name, options.case)]
    if not chosen or not cases:
        print(NOTHING)
        return 1
    options.work.mkdir(parents=True, exist_ok=True)
    return 1 if run(cases, chosen, options.work) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
