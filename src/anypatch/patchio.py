from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from n64_save_patches import (
    apsgba,
    apswrite,
    bdf,
    bps,
    imagesize,
    ipswrite,
    pmsr,
    ppf,
    rup,
    ups,
    vcdiff,
    zps,
)

HEADER_SUFFIX = ".hdr"


class Format(StrEnum):
    IPS = "ips"
    EBP = "ebp"
    ZPS = "zps"
    APS = "aps"
    APS_GBA = "aps-gba"
    UPS = "ups"
    BPS = "bps"
    PPF = "ppf"
    RUP = "rup"
    PMSR = "pmsr"
    BDF = "bdf"
    XDELTA = "xdelta"


SUFFIXES = {
    ".ips": Format.IPS,
    ".ebp": Format.EBP,
    ".zps": Format.ZPS,
    ".ip1": Format.ZPS,
    ".aps": Format.APS,
    ".ups": Format.UPS,
    ".bps": Format.BPS,
    ".ppf": Format.PPF,
    ".rup": Format.RUP,
    ".bdf": Format.BDF,
    ".bsdiff": Format.BDF,
    ".xdelta": Format.XDELTA,
    ".vcdiff": Format.XDELTA,
    ".xd3": Format.XDELTA,
    ".delta": Format.XDELTA,
}
FAULTS = (
    ipswrite.IpsError,
    apswrite.ApsError,
    apsgba.ApsGbaError,
    zps.ZpsError,
    ups.UpsError,
    bps.BpsError,
    ppf.PpfError,
    rup.RupError,
    pmsr.PmsrError,
    bdf.BdfError,
    vcdiff.VcdiffError,
    imagesize.ImageSizeError,
)
KNOWN = "IPS, IPS32, EBP, ZPS, APS, UPS, BPS, PPF, RUP, PMSR, BDF or xdelta"
MAGICS = (
    (ups.MAGIC, Format.UPS),
    (bps.MAGIC, Format.BPS),
    (ppf.MAGIC, Format.PPF),
    (rup.MAGIC, Format.RUP),
    (pmsr.MAGIC, Format.PMSR),
    (pmsr.YAY0, Format.PMSR),
    (bdf.MAGIC, Format.BDF),
    (vcdiff.MAGIC, Format.XDELTA),
)
APPLIERS: dict[Format, Callable[[bytes, bytes], bytes]] = {
    Format.IPS: ipswrite.apply,
    Format.EBP: ipswrite.apply,
    Format.APS: apswrite.apply,
    Format.APS_GBA: apsgba.apply,
    Format.UPS: ups.apply,
    Format.BPS: bps.apply,
    Format.PPF: ppf.apply,
    Format.RUP: rup.apply,
    Format.PMSR: pmsr.apply,
    Format.BDF: bdf.apply,
    Format.XDELTA: vcdiff.apply,
}
Builder = Callable[[bytes, bytes, str], bytes]
BUILDERS: dict[Format, Builder] = {
    Format.IPS: lambda before, after, _: ipswrite.build(before, after),
    Format.EBP: lambda before, after, text: ipswrite.build_ebp(
        before, after, {"description": text} if text else {}
    ),
    Format.APS: lambda before, after, text: apswrite.build(before, after, description=text),
    Format.UPS: lambda before, after, _: ups.build(before, after),
    Format.BPS: lambda before, after, _: bps.build(before, after),
    Format.PPF: lambda before, after, text: ppf.build(before, after, description=text),
    Format.RUP: lambda before, after, text: rup.build(before, after, description=text),
    Format.BDF: lambda before, after, _: bdf.build(before, after),
    Format.XDELTA: lambda before, after, _: vcdiff.build(before, after),
}
WRITABLE = (*BUILDERS, Format.ZPS)


class PatchError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Patch:
    name: str
    format: Format
    body: bytes
    binding: bytes | None


def format_of(path: str | Path) -> Format:
    found = SUFFIXES.get(Path(path).suffix.lower())
    if found is None:
        known = ", ".join(SUFFIXES)
        raise PatchError(f"{Path(path).name}: an unknown patch extension; use one of {known}")
    return found


def _detected(path: Path, body: bytes) -> Format:
    if body.startswith(ipswrite.MAGIC32):
        return Format.IPS
    if body.startswith(ipswrite.MAGIC):
        return Format.ZPS if SUFFIXES.get(path.suffix.lower()) == Format.ZPS else Format.IPS
    if apsgba.matches(body):
        return Format.APS_GBA
    if body.startswith(apswrite.MAGIC):
        return Format.APS
    found = next((kind for magic, kind in MAGICS if body.startswith(magic)), None)
    if found is None:
        raise PatchError(f"{path.name}: not a patch in any format read here: {KNOWN}")
    return found


def _header_beside(path: Path) -> bytes | None:
    wanted = (path.stem + HEADER_SUFFIX).lower()
    found = [one for one in path.parent.iterdir() if one.name.lower() == wanted]
    return found[0].read_bytes() if found else None


def read(path: str | Path) -> Patch:
    where = Path(path)
    try:
        body = where.read_bytes()
    except OSError as error:
        raise PatchError(f"cannot read {where}: {error.strerror or error}") from error
    kind = _detected(where, body)
    binding = _header_beside(where) if kind == Format.ZPS else None
    return Patch(where.name, kind, body, binding)


def _applied(source: bytes, patch: Patch) -> bytes:
    if patch.format == Format.ZPS:
        return zps.apply(source, patch.body, patch.binding)
    return APPLIERS[patch.format](source, patch.body)


def apply(source: bytes, patch: Patch) -> bytes:
    try:
        return _applied(source, patch)
    except FAULTS as error:
        raise PatchError(f"{patch.name}: {error}") from error


def encode(kind: Format, before: bytes, after: bytes, *, description: str = "") -> dict[str, bytes]:
    if kind not in WRITABLE:
        raise PatchError(f"{kind.value}: this format is read here, never written")
    try:
        if kind == Format.ZPS:
            payload, header = zps.build(before, after)
            return {".zps": payload, HEADER_SUFFIX: header}
        return {f".{kind.value}": BUILDERS[kind](before, after, description)}
    except (*FAULTS, ValueError) as error:
        raise PatchError(f"{kind.value}: {error}") from error


def files(
    path: str | Path, kind: Format, before: bytes, after: bytes, *, description: str = ""
) -> dict[Path, bytes]:
    target = Path(path)
    encoded = encode(kind, before, after, description=description)
    return {
        (target.with_suffix(HEADER_SUFFIX) if suffix == HEADER_SUFFIX else target): data
        for suffix, data in encoded.items()
    }


def write(
    path: str | Path, kind: Format, before: bytes, after: bytes, *, description: str = ""
) -> tuple[Path, ...]:
    planned = files(path, kind, before, after, description=description)
    for where, data in planned.items():
        where.write_bytes(data)
    return tuple(planned)
