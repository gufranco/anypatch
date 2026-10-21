from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from anypatch import conflicts, patchio
from anypatch.conflicts import Merged, Range
from anypatch.patchio import Format, Patch, PatchError

CLEAN_HINT = "; if this source already carries another patch, pass the clean one as well"
NOTHING = "nothing"
NAMES = {
    Format.IPS: ("IPS", NOTHING),
    Format.EBP: ("EBP", NOTHING),
    Format.ZPS: ("ZPS", "the .hdr beside it: the source's first 64 bytes, compared by CRC pair"),
    Format.APS: ("APS for N64", "cart code, country and CRC pair in its header"),
    Format.APS_GBA: ("APS for GBA", "the source size and a CRC16 of each 64 KiB block"),
    Format.UPS: ("UPS", "CRC32 of the source and of the result"),
    Format.BPS: ("BPS", "CRC32 of the source and of the result"),
    Format.PPF: ("PPF", "PPF 2.0 source size and block check; PPF 3.0 block check and undo data"),
    Format.RUP: ("RUP", "MD5 of the source and of the result, per file entry"),
    Format.RUP1: ("NINJA 1", "CRC32, MD5 and SHA-1 of the source, each skippable"),
    Format.PMSR: ("PMSR", "Paper Mario USA 1.0, by size and CRC32"),
    Format.BDF: ("BDF", NOTHING),
    Format.BSDIFF43: ("BSDIFF43, ENDSLEY", NOTHING),
    Format.GDIFF: ("GDIFF", NOTHING),
    Format.DPS: ("DPS", "the source size"),
    Format.HDIFF: ("HDiffPatch", "the source size"),
    Format.VPATCH: ("VPatch, NSIS", "MD5 or CRC32 of the source and of the result, per entry"),
    Format.JOJODIFF: ("JojoDiff", NOTHING),
    Format.DLDI: ("DLDI", "a DLDI section the app reserves, at least as large as the driver"),
    Format.XDELTA1: (
        "xdelta 1.1",
        "MD5 and size of the source and of the result, unless made with --noverify",
    ),
    Format.BSP: ("BSP", "whatever its script checks; a BSP written here checks the source SHA-1"),
    Format.PAT: ("PAT, FireFlower", "the original value of every byte it changes"),
    Format.XDELTA: ("xdelta", "an Adler-32 checksum of every window, when present"),
}
EXTRA_EXTENSIONS = {
    Format.APS_GBA: (".aps",),
    Format.BSDIFF43: (".bsdiff",),
    Format.RUP1: (".rup",),
    Format.PMSR: (".mod", ".pmsr"),
    Format.VPATCH: (".pat",),
    Format.XDELTA1: (".xdelta",),
}


@dataclass(frozen=True, slots=True)
class FormatInfo:
    format: Format
    name: str
    extensions: tuple[str, ...]
    reads: bool
    writes: bool
    binding: str


def _info(kind: Format) -> FormatInfo:
    name, binding = NAMES[kind]
    extensions = tuple(suffix for suffix, found in patchio.SUFFIXES.items() if found is kind)
    return FormatInfo(
        kind,
        name,
        extensions or EXTRA_EXTENSIONS[kind],
        True,
        kind in patchio.WRITABLE,
        binding,
    )


def formats() -> tuple[FormatInfo, ...]:
    return tuple(_info(kind) for kind in Format)


def identify(data: bytes, *, name: str) -> Format:
    return patchio.identify(data, name=name)


def load(
    data: bytes, *, name: str, binding: bytes | None = None, choices: tuple[int, ...] = ()
) -> Patch:
    return Patch(name, identify(data, name=name), data, binding, choices)


def _result(base: bytes, one: Patch, hinted: bool) -> bytes:
    try:
        return patchio.apply(base, one)
    except PatchError as error:
        raise PatchError(f"{error}{CLEAN_HINT if hinted else ''}") from error


def apply(
    source: bytes,
    patches: Sequence[Patch],
    *,
    clean: bytes | None = None,
    ignore: Sequence[Range] = (),
) -> Merged:
    base = source if clean is None else clean
    changes = [
        conflicts.change(one.name, base, _result(base, one, clean is None)) for one in patches
    ]
    return conflicts.merge(source, base, changes, ignore=ignore)


def make(before: bytes, after: bytes, kind: Format, *, description: str = "") -> dict[str, bytes]:
    return patchio.encode(kind, before, after, description=description)


def merge(
    source: bytes,
    patches: Sequence[Patch],
    kind: Format,
    *,
    clean: bytes | None = None,
    description: str = "",
    ignore: Sequence[Range] = (),
) -> dict[str, bytes]:
    base = source if clean is None else clean
    merged = apply(source, patches, clean=clean, ignore=ignore)
    return make(base, merged.image, kind, description=description)


def convert(
    source: bytes, patch: Patch, kind: Format, *, description: str = ""
) -> dict[str, bytes]:
    return make(source, patchio.apply(source, patch), kind, description=description)
