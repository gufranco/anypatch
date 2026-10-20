from __future__ import annotations

import importlib
import platform
import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from anypatch.version import VERSION

MIN_PYTHON = (3, 11)
CODECS = ("zlib", "bz2", "lzma")
NO_VERDICT = "nothing was checked, so there is no verdict to give"
FORMATS_SKIPPED = "not checked, because a codec is missing"

Importer = Callable[[str], object]


class CheckStatus(StrEnum):
    OK = "ok"
    WARNING = "warning"
    MISSING = "missing"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    status: CheckStatus
    detail: str


@dataclass(frozen=True, slots=True)
class DoctorReport:
    checks: tuple[Check, ...]

    @property
    def healthy(self) -> bool:
        if not self.checks:
            raise ValueError(NO_VERDICT)
        return all(check.status is not CheckStatus.FAILED for check in self.checks)


def _python(version: tuple[int, int, int]) -> Check:
    shown = ".".join(str(part) for part in version)
    if version[:2] < MIN_PYTHON:
        floor = ".".join(str(part) for part in MIN_PYTHON)
        detail = f"{shown}, older than {floor}, the oldest supported"
        return Check("python", CheckStatus.FAILED, detail)
    return Check("python", CheckStatus.OK, shown)


def _codec(name: str, importer: Importer) -> Check:
    try:
        importer(name)
    except ModuleNotFoundError:
        detail = f"this Python was built without {name}, which anypatch needs"
        return Check(name, CheckStatus.FAILED, detail)
    return Check(name, CheckStatus.OK, "available")


def _formats(codecs: tuple[Check, ...]) -> tuple[Check, ...]:
    if any(check.status is not CheckStatus.OK for check in codecs):
        return (Check("formats", CheckStatus.MISSING, FORMATS_SKIPPED),)
    selftest = importlib.import_module("anypatch.selftest")
    checks: tuple[Check, ...] = selftest.run()
    return checks


def diagnose(
    *,
    importer: Importer = importlib.import_module,
    python: tuple[int, int, int] | None = None,
) -> DoctorReport:
    running = python if python is not None else sys.version_info[:3]
    host = f"{platform.system()} {platform.machine()}"
    codecs = tuple(_codec(name, importer) for name in CODECS)
    return DoctorReport(
        (
            Check("anypatch", CheckStatus.OK, VERSION),
            _python(running),
            Check("platform", CheckStatus.OK, host),
            *codecs,
            *_formats(codecs),
        )
    )
