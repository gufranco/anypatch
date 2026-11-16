from __future__ import annotations

from collections.abc import Mapping

from anypatch.patchio import Format

OURS = "ours"
THEIRS = "theirs"
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
OPEN_VCDIFF_ADLER = (
    "open-vcdiff reads strict RFC 3284, not the per-window Adler-32 xdelta3 writes by default; "
    "anypatch writes that checksum the same way, and open-vcdiff rejects xdelta3's patch too"
)
OPEN_VCDIFF_EMPTY = "open-vcdiff encode never finishes when the target is empty"
OPEN_VCDIFF_CHECKSUMMED = (
    "identical",
    "empty-to-data",
    "first-byte",
    "last-byte",
    "grow-by-one",
    "shrink-by-one",
    "scattered",
    "long-run",
    "long-literal",
    "varint-0x7f",
    "varint-0x80",
    "varint-0x3fff",
    "varint-0x4000",
    "ips-eof-offset",
    "ips-run-at-eof-offset",
    "ips-last-offset",
    "ips-grow-to-limit",
    "ips-past-limit-low-change",
    "ips-past-limit-high-change",
    "ips-shrink-to-limit",
    "ips-shrink-below-limit",
    "aps-record-255",
    "aps-record-256",
    "gba-block-edge",
    "gba-partial-block",
    "ips-record-65535",
    "ips-record-65536",
    "gdiff-data-246",
    "gdiff-data-247",
    "gdiff-data-65535",
    "gdiff-data-65536",
    "gdiff-copy-255",
    "gdiff-copy-256",
    "gdiff-copy-65535",
    "gdiff-copy-65536",
    "gdiff-copy-past-ushort",
    "xdelta-window-0x7fffff",
    "xdelta-window-0x800000",
    "xdelta-window-0x800001",
    "xdelta-window-0x1000001",
    "pmsr-base-edit",
    "pmsr-base-grow",
)
NINJA1_TOOLS = ("ninja1", "ninja1-bz", "ninja1-text", "ninja1-tz")
NINJA1_EMPTY = "NINJA 1.01 on PHP 8 fails on an empty file, where its fread of zero bytes throws"
XDELTA1_EMPTY = (
    "xdelta1 patch exits 2 without a message when the result is empty, "
    "on the patch xdelta1 delta writes for that case as well"
)
NINJA1_SHRINK = "NINJA 1 cannot shrink a file, and NINJA 1.01 writes the patch anyway"
NINJA1_LARGE = (
    "NINJA 1.01 writes a record 0x200 bytes before its change in a file over 30 MiB, "
    "such as 0x27FFDF8 for a change at 0x27FFFF8"
)
IGIR_GROWTH = (
    "igir's IOFile.writeAt extends a growing file by its whole current size as well, "
    "so zeros follow the target"
)
IGIR_SHRINK = (
    "igir patches a copy of the source in place and never truncates it to a smaller target"
)
IGIR_UPS_SHRINK = (
    "igir never cuts a UPS result to the output size it records, so a smaller target keeps "
    "its XOR-cleared tail"
)
IGIR_ZERO_WIDTH = (
    "igir reads a NINJA number with readUIntLE, which throws on the zero-byte width "
    "NINJA 2.0 itself writes for a size of 0"
)
IGIR_GBA_WHOLE = (
    "igir writes every APS for GBA block in full and never cuts the result to the target "
    "size the header records"
)
IGIR_GBA_BLOCKS = (
    "igir reads 1 MiB of XOR data per APS for GBA record where a record holds a 64 KiB "
    "block, so a patch of more than one block is misread"
)
IGIR_RUN = "igir takes a VCDIFF RUN's byte at the target window offset, not the data section's"
IGIR_GROWN = (
    "grow-by-one",
    "varint-0x7f",
    "varint-0x80",
    "varint-0x3fff",
    "varint-0x4000",
    "ips-grow-to-limit",
    "pmsr-base-grow",
)
IGIR_SHRUNK = ("data-to-empty", "shrink-by-one", "ips-shrink-to-limit", "ips-shrink-below-limit")
IGIR_GBA_GROWN = ("empty-to-data", "varint-0x7f", "varint-0x80", "varint-0x3fff", "varint-0x4000")
IGIR_GBA_SINGLE = ("data-to-empty", "shrink-by-one", "xdelta-window-0x7fffff")
IGIR_GBA_MULTI = (
    "grow-by-one",
    "scattered",
    "long-run",
    "long-literal",
    "ips-grow-to-limit",
    "ips-shrink-to-limit",
    "ips-shrink-below-limit",
    "gba-block-edge",
    "ips-record-65535",
    "ips-record-65536",
    "gdiff-data-65535",
    "gdiff-data-65536",
    "gdiff-copy-65535",
    "gdiff-copy-65536",
    "gdiff-copy-past-ushort",
    "xdelta-window-0x800001",
    "xdelta-window-0x1000001",
    "pmsr-base-edit",
    "pmsr-base-grow",
)
IGIR_IN_PLACE = (
    Format.IPS,
    Format.APS,
    Format.UPS,
    Format.PPF,
    Format.RUP,
    Format.DPS,
    Format.XDELTA,
)
IGIR_KNOWN: Mapping[tuple[str, Format, str, str], str] = {
    **{("igir", kind, OURS, case): IGIR_GROWTH for kind in IGIR_IN_PLACE for case in IGIR_GROWN},
    **{("igir", Format.EBP, OURS, case): IGIR_GROWTH for case in IGIR_GROWN[:-1]},
    **{
        ("igir", kind, OURS, case): IGIR_SHRINK
        for kind in (Format.IPS, Format.APS, Format.DPS, Format.XDELTA)
        for case in IGIR_SHRUNK
    },
    **{("igir", Format.RUP, OURS, case): IGIR_SHRINK for case in IGIR_SHRUNK[1:]},
    **{
        ("igir", Format.RUP, OURS, case): IGIR_ZERO_WIDTH
        for case in ("empty-to-data", "data-to-empty")
    },
    **{("igir", Format.UPS, OURS, case): IGIR_UPS_SHRINK for case in IGIR_SHRUNK},
    **{("igir", Format.APS_GBA, OURS, case): IGIR_GROWTH for case in IGIR_GBA_GROWN},
    **{("igir", Format.APS_GBA, OURS, case): IGIR_GBA_WHOLE for case in IGIR_GBA_SINGLE},
    **{("igir", Format.APS_GBA, OURS, case): IGIR_GBA_BLOCKS for case in IGIR_GBA_MULTI},
    **{
        ("igir", Format.XDELTA, OURS, case): IGIR_RUN
        for case in ("long-run", "ips-run-at-eof-offset")
    },
}
KNOWN: Mapping[tuple[str, Format, str, str], str] = {
    **IGIR_KNOWN,
    ("ninja1", Format.RUP1, OURS, "empty-to-data"): NINJA1_EMPTY,
    ("xdelta1", Format.XDELTA1, OURS, "data-to-empty"): XDELTA1_EMPTY,
    **{
        (tool, Format.RUP1, THEIRS, case): reason
        for tool in NINJA1_TOOLS
        for case, reason in (
            ("empty-to-data", NINJA1_EMPTY),
            ("data-to-empty", NINJA1_EMPTY),
            ("shrink-by-one", NINJA1_SHRINK),
            ("ips-shrink-to-limit", NINJA1_SHRINK),
            ("ips-shrink-below-limit", NINJA1_SHRINK),
            ("pmsr-base-edit", NINJA1_LARGE),
            ("pmsr-base-grow", NINJA1_LARGE),
        )
    },
    **{
        ("open-vcdiff", Format.XDELTA, OURS, case): OPEN_VCDIFF_ADLER
        for case in OPEN_VCDIFF_CHECKSUMMED
    },
    **{
        (tool, Format.XDELTA, THEIRS, "data-to-empty"): OPEN_VCDIFF_EMPTY
        for tool in ("open-vcdiff", "open-vcdiff-sdch", "open-vcdiff-matches")
    },
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
