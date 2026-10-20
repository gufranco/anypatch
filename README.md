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

> [!WARNING]
> This project is experimental and in active development. The patch formats are moving here from [n64-save-patches](https://github.com/gufranco/n64-save-patches-python) and arrive over the next releases. Commands and the library API may change without notice.

anypatch is one library and one command line over the same code. Every capability is a typed Python function and a command, and the command only calls the function. The library needs nothing beyond the Python standard library; the command line adds Typer.

## Usage

```console
$ anypatch doctor
anypatch     0.1.0
python       3.14.0
platform     Darwin arm64
zlib         available
bz2          available
lzma         available
```

```python
from anypatch import doctor

report = doctor.diagnose()
print(report.healthy)
```

`doctor` exits 0 when no check failed and 1 when one did. A codec missing from the running Python is reported as `missing`, and the formats that need it are not read; that alone does not fail the install. `anypatch doctor --json` prints the same report as JSON with `healthy` and `checks`.

## Commands

| Command | Library | Answers |
|:--|:--|:--|
| `anypatch doctor [--json]` | `anypatch.doctor.diagnose()` | Whether this installation works: version, Python, platform, and each standard library codec the formats use |
| `anypatch --version` | `anypatch.version.VERSION` | The installed version |

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
