# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [semantic versioning](https://semver.org/spec/v2.0.0.html). Release notes for each tag are on the [releases page](https://github.com/gufranco/anypatch/releases).

## Unreleased

### What's new

- NINJA 1 patches, binary or text and plain or zlib, are read with their CRC32, MD5 and SHA-1 checks, and written in binary with `--format rup1`.
- DPS patches are read and written. The format has no magic, so a DPS patch is recognised by its `.dps` extension.
- VCDIFF reads open-vcdiff's S version, with interleaved windows and its zero-seeded Adler-32, and application code tables in both the RFC 3284 layout igir reads and the layout open-vcdiff reads. Reference patches from open-vcdiff are in the suite.
- PAT, the FireFlower format for Neo Geo hacks and the output of `fc /b`, is read and written with `--format pat`. It holds only byte changes, so a size change is refused.
- A RUP patch that names a ROM type is applied the way NINJA 2.0 applies it: the dump is converted to NINJA's common form before the MD5 check, removing iNES, Famtasia, copier and Lynx headers and undoing UNIF, HiROM, SMD and v64 layouts, and NES, NSRT and Lynx headers go back on afterwards. A dump that does not convert is compared as it is.
- Patches are exchanged with Flips, ApplyPPF, MakePPF, bsdiff4 and NINJA 2.0 as well, on every generated limit case.

### Fixes

- PPF compares only the block-check bytes a short dump holds, and identical files get one no-op record, since ApplyPPF loops forever and RomPatcher.js crashes on a PPF with no records.

## 0.5.0

### What's new

- BSDIFF43, the ENDSLEY variant of bsdiff that keeps one bzip2 stream, is read and written with `--format bsdiff43`.
- GDIFF, the 1997 W3C generic diff format, is read and written with every command form, including 64-bit copy positions.
- APS is written without the N64 header when the source is not an N64 ROM, and such patches from RomPatcher.js are read. An empty or short source can now be patched.
- BPS carries `--description` as its metadata, and EBP writes the title, author and description fields EBPatcher and CoilSnake read.
- Every format is tested on generated files at its own limits, and those files are exchanged with xdelta3, bsdiff, javaxdelta and RomPatcher.js in both directions.

### Fixes

- IPS stays plain IPS for an image over 16 MiB whose changes all sit below 16 MiB, and refuses cleanly instead of crashing when shrinking to exactly 16 MiB. EBP and ZPS follow the same rule.
- IPS reads a record at offset 0x454F46, which RomPatcher.js writes, when the bytes after `EOF` are not a size or metadata.
- A VCDIFF window or instruction larger than its declared size is refused before any output is produced, and a window past the size ceiling is refused before it is decoded.
- PPF reads the GI block check for any nonzero image type, as ApplyPPF does.
- APS for GBA accepts a short last block's CRC16 with or without zero padding.
- ZPS refuses a source shorter than its 64-byte binding instead of writing a patch nothing could apply.

## 0.4.0

### What's new

- APS for GBA and PMSR are written as well as read, with `--format aps-gba` and `--format pmsr`. A PMSR patch is only made against Paper Mario USA 1.0.

## 0.3.0

### What's new

- APS patches made for byte-swapped `.v64` dumps are read and applied to the native dump. All 21 community APS patches for the Mr. Backup Z64 apply and pass the boot checksum.
- The README no longer calls the formats experimental.

## 0.2.0

### What's new

- Read IPS, IPS32, EBP, ZPS, APS for N64 and GBA, UPS, BPS, PPF 1.0 to 3.0, RUP, PMSR with or without Yay0, BDF and xdelta, and write all of them except APS for GBA and PMSR. The format code moved here from n64-save-patches with its history.
- `anypatch make`, `apply`, `merge`, `convert`, `info` and `formats`, each the same as the function of that name in `anypatch.api`.
- Applying several patches compares what each changes on the clean source and refuses any two that write different bytes to one place, listing every range.
- `doctor` writes and replays a patch in every writable format and decodes the two read-only ones.

## 0.1.0

### What's new

- `anypatch doctor` and `anypatch.doctor.diagnose()` report the version, Python, platform and the standard library codecs the formats use, as text or as JSON.
- Installable with Homebrew from this repository, and usable as a library with no dependency outside the standard library.
