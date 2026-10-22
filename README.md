<div align="center">

<h1>anypatch</h1>

<strong>Read, write, merge and convert binary patches in every documented format</strong>

<br>
<br>

English | [日本語](README.ja.md) | [简体中文](README.zh-Hans.md) | [繁體中文 (香港)](README.zh-HK.md)

<br>

[![CI](https://github.com/gufranco/anypatch/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/anypatch/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)](pyproject.toml)
[![Types](https://img.shields.io/badge/mypy-strict-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

---

anypatch is one library and one command line over the same code. Every capability is a typed Python function and a command, and the command only calls the function. The library needs nothing beyond the Python standard library; the command line adds Typer.

## Usage

```console
$ anypatch make clean.bin modified.bin -o title.bps
wrote          title.bps, 38 bytes
$ anypatch apply clean.bin title.bps fix.ips -o out.bin
applied        title.bps, fix.ips
wrote          out.bin, 65,536 bytes
$ anypatch apply clean.bin title.bps clash.ups -o never.bin
the patches conflict:
  0x000104..0x000106: title.bps writes 5449, clash.ups writes 5858
$ anypatch merge clean.bin title.bps fix.ips -o both.xdelta
wrote          both.xdelta, 52 bytes
$ anypatch info title.bps
format         BPS
bound by       CRC32 of the source and of the result
size           38 bytes
```

```python
from pathlib import Path

from anypatch import api
from anypatch.patchio import Format

clean = Path("clean.bin").read_bytes()
patches = [api.load(Path(name).read_bytes(), name=name) for name in ("title.bps", "fix.ips")]
Path("out.bin").write_bytes(api.apply(clean, patches).image)
Path("both.xdelta").write_bytes(api.merge(clean, patches, Format.XDELTA)[".xdelta"])
```

## Commands

| Command | Library, in `anypatch.api` | Answers |
|:--|:--|:--|
| `anypatch make <before> <after> -o <patch>` | `make(before, after, format)` | The patch that turns one file into another. The extension of `-o` picks the format unless `--format` names one |
| `anypatch apply <source> <patch>... -o <out>` | `apply(source, patches)` | The source with every patch applied, after the conflict check |
| `anypatch merge <source> <patch>... -o <patch>` | `merge(source, patches, format)` | One patch that does what all of them do |
| `anypatch convert <source> <patch> -o <patch>` | `convert(source, patch, format)` | The same change in another format |
| `anypatch revert <image> <patch> -o <out>` | `revert(image, patch)` | The source a patched image came from, for UPS and for PPF with undo data |
| `anypatch info <patch> [--json]` | `identify(data, name=...)` | Which format a patch is and what binds it to its source |
| `anypatch formats [--json]` | `formats()` | Every format, whether it is read and written, and its extensions |
| `anypatch doctor [--json]` | `anypatch.doctor.diagnose()` | Whether this installation works: version, Python, platform, the codecs, and a round trip through every format |
| `anypatch --version` | `anypatch.version.VERSION` | The installed version |

`--clean <file>` on `apply` and `merge` names the clean source when the input already carries a patch. `--description` sets the text an APS, BPS, EBP, PPF or RUP patch carries. `--choice <n>` on `apply` answers a BSP menu, once per menu in order. Every output is computed before anything is written, so a refusal leaves no file behind. Errors go to standard error and the exit code is 1.

## Formats

| Format | Read | Written | Extensions | Bound to its source by |
|:--|:--|:--|:--|:--|
| IPS | yes | yes | `.ips` | Nothing. A change past 16 MiB is written as IPS32 |
| EBP | yes | yes | `.ebp` | Nothing. IPS with JSON metadata after `EOF` |
| ZPS | yes | yes | `.zps`, `.ip1` | The `.hdr` beside it, the source's first 64 bytes, compared by CRC pair |
| APS for N64 | yes, native or byte-swapped | native | `.aps` | Cart code, country and CRC pair when the source is an N64 ROM; otherwise the header without them, as RomPatcher.js writes it |
| APS for GBA | yes | yes, with `--format aps-gba` | `.aps` | The source size and a CRC16 of each 64 KiB block; a short last block is read with or without zero padding. RomPatcher.js reads one only when the size stays the same and a short last block is unchanged |
| UPS | yes | yes | `.ups` | CRC32 of the source and of the result |
| BPS | yes | yes | `.bps` | CRC32 of the source and of the result |
| PPF 1.0, 2.0, 3.0 | yes | as 3.0 with undo data | `.ppf` | PPF 2.0 source size and block check; PPF 3.0 block check and undo data |
| RUP, NINJA 2.0 | yes | yes | `.rup` | MD5 of the source and of the result, per file entry, taken after NINJA's conversion for the entry's ROM type: headers off, layouts undone |
| NINJA 1 | yes, binary and text, plain or zlib | binary, with `--format rup1` | `.rup` | CRC32, MD5 and SHA-1 of the source, each skippable, after NINJA 1's conversion for SNES, Mega Drive and Game Boy |
| PMSR | yes | yes, with `--format pmsr` | `.mod`, `.pmsr` | Paper Mario USA 1.0, by size and CRC32; read plain or inside Yay0, written plain |
| BDF, bsdiff 4 | yes | yes | `.bdf`, `.bsdiff` | Nothing |
| BSDIFF43, ENDSLEY | yes | yes, with `--format bsdiff43` | `.bsdiff` | Nothing |
| GDIFF | yes | yes | `.gdiff`, `.gdf` | Nothing |
| PAT, FireFlower | yes, also `fc /b` output | yes, when the size stays the same | `.pat` | The original value of every byte it changes |
| DPS | yes, by the `.dps` extension, since the format has no magic | yes | `.dps` | The source size |
| HDiffPatch | HDIFF13 and HDIFFSF20, uncompressed or with zlib, bzip2, LZMA or LZMA2 | HDIFF13, uncompressed | `.hdiff` | The source size |
| VPatch, NSIS | yes, in MD5 and CRC32 mode, with every entry of a multi-source file, and with the header found through the pointer at the end of an installer | one MD5 entry, with `--format vpatch` | `.pat` | MD5 or CRC32 of the source and of the result, per entry |
| JojoDiff | yes, by the `.jdf` extension, since the format has no magic | yes, with `--format jdf` | `.jdf` | Nothing |
| DLDI | yes, injecting a driver into the DLDI section of a DS app and relocating it as dlditool does | no, a driver is built, not diffed | `.dldi` | A DLDI section the app reserves, at least as large as the driver |
| xdelta 1.1 | `%XDZ004%`, plain or gzip, with or without its MD5 checks | `%XDZ004%`, plain, with `--format xdelta1` | `.xdelta` | MD5 and size of the source and of the result, unless made with `--noverify`. Patches older than 1.1 and patches made between gzip-decompressed files are refused by name |
| BSP | yes, by the `.bsp` extension, since the format has no magic: every instruction of the 0.6 specification, nested patches and embedded IPS. A menu takes the next `--choice` given to `apply`, or `choices` in `anypatch.api.load`; without one it is refused with its options listed | yes, a script that checks the source SHA-1 and writes each change | `.bsp` | Whatever its script checks; a BSP written here checks the source SHA-1 |
| xdelta, VCDIFF | yes | yes | `.xdelta`, `.vcdiff`, `.xd3`, `.delta` | An Adler-32 checksum of every window, when present. Reads xdelta3 output with no secondary compression, LZMA, DJW or FGK, open-vcdiff's interleaved and checksummed S version, and application code tables in the RFC 3284 and open-vcdiff layouts |

The contents decide the format; only an IPS body named `.zps` or `.ip1` is read as ZPS. Every patch is applied to the clean source on its own, and the bytes each one changes are compared. Two patches that write different values to one byte are refused, with every range and both values listed; identical writes merge. A patch whose format carries a source checksum is refused on any other file, naming both values, and when the source already holds the result it is reported as already applied. A patch that claims a result larger than both 1 GiB and its source is refused before anything is allocated.

## Preservation and legal use

anypatch exists for preservation and interoperability. It ships no ROMs and no patches, and it carries no links to where to obtain them. You supply the files you work on, and you are responsible for holding them legally: an image you created from your own cartridge, a patch you are licensed to use. Every format was learned clean-room from a public specification or an open implementation, each listed in [NOTICE.md](NOTICE.md); no third-party code was copied. The suite that gates every change, `uv run pytest`, runs entirely on synthetic data and contacts no external site.

The optional interop cross-checks use reference tools this project neither ships nor downloads. Supply each one yourself, legally obtained, in a local `external/` folder that is gitignored. [artifacts.manifest.json](artifacts.manifest.json) lists every expected file by name and SHA-256 so you can confirm what you place there; no download location is recorded, by design.

## Install

### Homebrew

```bash
brew install gufranco/tap/anypatch
anypatch doctor
```

The formula lives in [gufranco/homebrew-tap](https://github.com/gufranco/homebrew-tap), a shared formula-only tap, so tapping it is a fast clone. `brew install --HEAD gufranco/tap/anypatch` builds the tip of `main` instead of the latest release.

### As a dependency of another project

anypatch is not published to PyPI. Depend on a release tag:

```toml
dependencies = ["anypatch @ git+https://github.com/gufranco/anypatch@v0.1.0"]
```

Add the `cli` extra, `anypatch[cli] @ git+...`, only if that project also needs the command. Without it, `anypatch` on the command line says how to get it and exits 1.

### From source

| Tool | Version |
|:--|:--|
| Python | 3.11 or newer |
| uv | any recent |

```bash
git clone https://github.com/gufranco/anypatch.git
cd anypatch
uv sync
uv run anypatch doctor
```

`uv run python -m anypatch` runs the same command line.

## Development

| Gate | Command |
|:--|:--|
| Tests, with the 100% statement and branch gate | `uv run pytest --cov` |
| Exchange the boundary files with a reference tool | `PYTHONPATH=src python scripts/interop.py --tool xdelta3 --work <dir>` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format --check .` |
| Types, strict | `uv run mypy` |
| JSON and YAML format | `pnpm run format:check` |

`git config core.hooksPath .githooks` runs the commit-message check and the fast gates before each commit. Commits follow [Conventional Commits](https://www.conventionalcommits.org/); semantic-release reads them to cut each release, and while the version is 0.x a breaking change raises the minor number.

## Support

| Need | Where |
|:--|:--|
| Bug report | [GitHub Issues](https://github.com/gufranco/anypatch/issues) |
| Security report | [Security policy](SECURITY.md) |
| Contributing | [Contribution guide](CONTRIBUTING.md) |
| Conduct | [Code of conduct](CODE_OF_CONDUCT.md) |

## License

[MIT](LICENSE). The formats were learned from the specifications and open implementations listed in [NOTICE.md](NOTICE.md).
