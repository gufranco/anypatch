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

from interop_known import KNOWN, OURS, THEIRS

from anypatch import api
from anypatch import boundaries_test_support as boundaries
from anypatch.formats import dldi_vectors_test_support as dldi_cases
from anypatch.patchio import Format, PatchError

TIMEOUT = 300
OPEN_VCDIFF_TIMEOUT = 120
LOG_TAIL = 2000
REPORT_WIDTH = 600
ROMJS_WRITES = (Format.IPS, Format.EBP, Format.UPS, Format.BPS, Format.PPF, Format.APS, Format.RUP)
ROMJS_READS = (*ROMJS_WRITES, Format.BDF, Format.APS_GBA, Format.PMSR)
XDELTA_CODERS = ("none", "lzma", "djw", "fgk")
IGIR_READS = (
    Format.IPS,
    Format.EBP,
    Format.APS,
    Format.APS_GBA,
    Format.UPS,
    Format.BPS,
    Format.PPF,
    Format.RUP,
    Format.DPS,
    Format.XDELTA,
)
NOTHING = "nothing matched the --tool and --case filters"
DLDITOOL = "dlditool"


@dataclass(frozen=True, slots=True)
class Exchange:
    tool: str
    kind: Format
    make: str | None
    apply: str | None
    timeout: int | None = None


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


def _open_vcdiff() -> list[Exchange]:
    create = "vcdiff encode -dictionary {source} -target {target} -delta {patch}"
    apply = "vcdiff decode -dictionary {source} -delta {patch} -target {out}"
    return [
        Exchange("open-vcdiff", Format.XDELTA, create, apply, OPEN_VCDIFF_TIMEOUT),
        Exchange(
            "open-vcdiff-sdch",
            Format.XDELTA,
            f"{create} -interleaved -checksum",
            None,
            OPEN_VCDIFF_TIMEOUT,
        ),
        Exchange(
            "open-vcdiff-matches",
            Format.XDELTA,
            f"{create} -target_matches",
            None,
            OPEN_VCDIFF_TIMEOUT,
        ),
    ]


def _ninja1() -> list[Exchange]:
    create = "$NINJA1 -%s raw {source} {target} {patch}"
    apply = "cp {source} {out} && printf 'n\\n' | $NINJA1 -p {patch} {out}"
    return [
        Exchange("ninja1", Format.RUP1, create % "b", apply),
        Exchange("ninja1-bz", Format.RUP1, create % "bz", None),
        Exchange("ninja1-text", Format.RUP1, create % "t", None),
        Exchange("ninja1-tz", Format.RUP1, create % "tz", None),
    ]


def _hdiffpatch() -> list[Exchange]:
    create = "hdiffz -f -c-%s {source} {target} {patch}"
    apply = "hpatchz -f {source} {patch} {out}"
    return [
        Exchange("hdiffpatch", Format.HDIFF, create % "zlib", apply),
        Exchange("hdiffpatch-bzip2", Format.HDIFF, create % "bzip2", None),
        Exchange("hdiffpatch-lzma2", Format.HDIFF, create % "lzma2", None),
        Exchange("hdiffpatch-sd", Format.HDIFF, f"{create % 'lzma'} -SD", None),
    ]


def _xdelta1() -> list[Exchange]:
    create = "xdelta1 delta -p %s {source} {target} {patch}; [ $? -le 1 ]"
    apply = "xdelta1 patch {patch} {source} {out}"
    return [
        Exchange("xdelta1", Format.XDELTA1, create % "-0", apply),
        Exchange("xdelta1-gzip", Format.XDELTA1, create % "-6", None),
        Exchange("xdelta1-noverify", Format.XDELTA1, create % "-0 -n", None),
    ]


def _igir() -> list[Exchange]:
    apply = 'node scripts/igir/harness.mjs "$IGIR" {patch} {source} {out}'
    return [Exchange("igir", kind, None, apply) for kind in IGIR_READS]


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
        *_open_vcdiff(),
        *_hdiffpatch(),
        *_flips(),
        *_ninja1(),
        *_ppf(),
        Exchange(
            "ninja",
            Format.RUP,
            "mkdir -p {patch}.a {patch}.b && cp {source} {patch}.a/f && cp {target} {patch}.b/f"
            " && $NINJA {patch}.a {patch}.b {patch} raw none",
            "cp {source} {out} && $NINJA {patch} {out}",
        ),
        Exchange("ninja", Format.PAT, None, "cp {source} {out} && $NINJA {patch} {out}"),
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
            "vpatch",
            Format.VPATCH,
            "genpat {source} {target} {patch}",
            "vpatch-apply {source} {patch} {out}",
        ),
        Exchange(
            "jojodiff",
            Format.JOJODIFF,
            "jdiff {source} {target} {patch}; [ $? -le 1 ]",
            "jpatch {source} {patch} {out}",
        ),
        *_xdelta1(),
        *_igir(),
        Exchange(
            "bsppatch", Format.BSP, None, 'node "$BSP_HARNESS" "$BSPPATCH" {patch} {source} {out}'
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


def _run(template: str, paths: dict[str, Path], timeout: int | None = None) -> str:
    limit = timeout or TIMEOUT
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
                timeout=limit,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return f"timed out after {limit} s: {command} {_tail(log)}".strip()
    if done.returncode != 0:
        return f"exit {done.returncode}: {command} {_tail(log)}".strip()
    return ""


def _ours_read_by_them(case: boundaries.Boundary, one: Exchange, paths: dict[str, Path]) -> str:
    files = api.make(case.source, case.target, one.kind)
    paths["patch"].write_bytes(files[f".{one.kind.value}"])
    failed = _run(one.apply or "", paths, one.timeout)
    if failed:
        return failed
    made = paths["out"].read_bytes() if paths["out"].exists() else b""
    return "" if made == case.target else "their output differs from the target"


def _theirs_read_by_us(case: boundaries.Boundary, one: Exchange, paths: dict[str, Path]) -> str:
    failed = _run(one.make or "", paths, one.timeout)
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


def _dldi(case: dldi_cases.Case, work: Path) -> str:
    paths = {"app": work / "app.nds", "driver": work / "driver.dldi", "out": work / "app.nds"}
    paths["app"].write_bytes(case.app)
    paths["driver"].write_bytes(case.driver)
    failed = _run(f"{DLDITOOL} {{driver}} {{app}}", paths)
    if failed:
        return failed
    ours = api.apply(case.app, [api.load(case.driver, name=paths["driver"].name)]).image
    return "" if ours == paths["app"].read_bytes() else "our output differs from dlditool's"


def run_dldi(work: Path) -> int:
    failures = {case.name: _dldi(case, work) for case in dldi_cases.cases()}
    for name, detail in failures.items():
        mark = Mark.FAIL if detail else Mark.PASS
        print(f"{mark} {name} {DLDITOOL} dldi theirs {detail}".rstrip(), flush=True)
    failed = sum(1 for detail in failures.values() if detail)
    print(f"{len(failures) - failed} passed, {failed} failed")
    return failed


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
    if options.tool == [DLDITOOL]:
        options.work.mkdir(parents=True, exist_ok=True)
        return 1 if run_dldi(options.work) else 0
    chosen = [one for one in exchanges() if _tool_matches(one.tool, options.tool)]
    cases = [case for case in boundaries.cases() if _matches(case.name, options.case)]
    if not chosen or not cases:
        print(NOTHING)
        return 1
    options.work.mkdir(parents=True, exist_ok=True)
    return 1 if run(cases, chosen, options.work) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
