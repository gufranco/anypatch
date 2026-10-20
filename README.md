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
$ anypatch make clean.bin hacked.bin -o title.bps
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
| `anypatch info <patch> [--json]` | `identify(data, name=...)` | Which format a patch is and what binds it to its source |
| `anypatch formats [--json]` | `formats()` | Every format, whether it is read and written, and its extensions |
| `anypatch doctor [--json]` | `anypatch.doctor.diagnose()` | Whether this installation works: version, Python, platform, the codecs, and a round trip through every format |
| `anypatch --version` | `anypatch.version.VERSION` | The installed version |

`--clean <file>` on `apply` and `merge` names the clean source when the input already carries a patch. `--description` sets the text an APS, EBP, PPF or RUP patch carries. Every output is computed before anything is written, so a refusal leaves no file behind. Errors go to standard error and the exit code is 1.

## Formats

| Format | Read | Written | Extensions | Bound to its source by |
|:--|:--|:--|:--|:--|
| IPS | yes | yes | `.ips` | Nothing. A change past 16 MiB is written as IPS32 |
| EBP | yes | yes | `.ebp` | Nothing. IPS with JSON metadata after `EOF` |
| ZPS | yes | yes | `.zps`, `.ip1` | The `.hdr` beside it, the source's first 64 bytes, compared by CRC pair |
| APS for N64 | yes, native or byte-swapped | native | `.aps` | Cart code, country and CRC pair in its header |
| APS for GBA | yes | yes, with `--format aps-gba` | `.aps` | The source size and a CRC16 of each 64 KiB block. RomPatcher.js reads one that grows the file only with its source check off |
| UPS | yes | yes | `.ups` | CRC32 of the source and of the result |
| BPS | yes | yes | `.bps` | CRC32 of the source and of the result |
| PPF 1.0, 2.0, 3.0 | yes | as 3.0 with undo data | `.ppf` | PPF 2.0 source size and block check; PPF 3.0 block check and undo data |
| RUP, NINJA 2.0 | yes | yes | `.rup` | MD5 of the source and of the result, per file entry |
| PMSR | yes | yes, with `--format pmsr` | `.mod`, `.pmsr` | Paper Mario USA 1.0, by size and CRC32; read plain or inside Yay0, written plain |
| BDF, bsdiff 4 | yes | yes | `.bdf`, `.bsdiff` | Nothing |
| GDIFF | yes | yes | `.gdiff`, `.gdf` | Nothing |
| xdelta, VCDIFF | yes | yes | `.xdelta`, `.vcdiff`, `.xd3`, `.delta` | An Adler-32 checksum of every window, when present. Reads xdelta3 output with no secondary compression, LZMA, DJW or FGK |

The contents decide the format; only an IPS body named `.zps` or `.ip1` is read as ZPS. Every patch is applied to the clean source on its own, and the bytes each one changes are compared. Two patches that write different values to one byte are refused, with every range and both values listed; identical writes merge. A patch whose format carries a source checksum is refused on any other file, naming both values, and when the source already holds the result it is reported as already applied. A patch that claims a result larger than both 1 GiB and its source is refused before anything is allocated.

## Install

### Homebrew

```bash
brew tap gufranco/anypatch https://github.com/gufranco/anypatch
brew install gufranco/anypatch/anypatch
anypatch doctor
```

The tap needs the URL because the repository is not named `homebrew-anypatch`. `brew install --HEAD gufranco/anypatch/anypatch` builds the tip of `main` instead of the latest release.

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
