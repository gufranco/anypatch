from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from n64_save_patches import apswrite, ipswrite, vcdiff, zps

HEADER_SUFFIX = ".hdr"


class Format(StrEnum):
    IPS = "ips"
    ZPS = "zps"
    APS = "aps"
    XDELTA = "xdelta"


SUFFIXES = {
    ".ips": Format.IPS,
    ".zps": Format.ZPS,
    ".ip1": Format.ZPS,
    ".aps": Format.APS,
    ".xdelta": Format.XDELTA,
    ".vcdiff": Format.XDELTA,
    ".xd3": Format.XDELTA,
    ".delta": Format.XDELTA,
}
FAULTS = (ipswrite.IpsError, apswrite.ApsError, zps.ZpsError, vcdiff.VcdiffError)


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
    if body.startswith(ipswrite.MAGIC):
        return Format.ZPS if SUFFIXES.get(path.suffix.lower()) == Format.ZPS else Format.IPS
    if body.startswith(apswrite.MAGIC):
        return Format.APS
    if body.startswith(vcdiff.MAGIC):
        return Format.XDELTA
    raise PatchError(f"{path.name}: not an IPS, ZPS, APS or xdelta patch")


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
    if patch.format == Format.IPS:
        return ipswrite.apply(source, patch.body)
    if patch.format == Format.ZPS:
        return zps.apply(source, patch.body, patch.binding)
    if patch.format == Format.APS:
        return apswrite.apply(source, patch.body)
    return vcdiff.apply(source, patch.body)


def apply(source: bytes, patch: Patch) -> bytes:
    try:
        return _applied(source, patch)
    except FAULTS as error:
        raise PatchError(f"{patch.name}: {error}") from error


def encode(kind: Format, before: bytes, after: bytes, *, description: str = "") -> dict[str, bytes]:
    try:
        if kind == Format.IPS:
            return {".ips": ipswrite.build(before, after)}
        if kind == Format.ZPS:
            payload, header = zps.build(before, after)
            return {".zps": payload, HEADER_SUFFIX: header}
        if kind == Format.APS:
            return {".aps": apswrite.build(before, after, description=description)}
        return {".xdelta": vcdiff.build(before, after)}
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
