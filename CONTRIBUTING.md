# Contributing

## Getting it running

```bash
git clone https://github.com/gufranco/anypatch.git
cd anypatch
uv sync
git config core.hooksPath .githooks
uv run pytest --cov
```

The suite passes on a clean checkout with no network. Every file a test needs is synthesised, and every reference patch is stored as data in the repository.

## The gates

| Gate | Command |
|:--|:--|
| Format | `uv run ruff format --check .` |
| Lint | `uv run ruff check .` |
| Types | `uv run mypy` |
| Tests and coverage | `uv run pytest --cov` |
| JSON and YAML format | `pnpm run format:check` |

Coverage is gated at 100% of statements and branches. When a branch cannot be reached by any input, delete it rather than excuse it.

## What a new format needs

1. The specification or open implementation it was learned from, added to [NOTICE.md](NOTICE.md) with its license.
2. Reference patches written by another program or printed in the specification, stored as data, and a test that applies each one to its target.
3. When a program exists that reads or writes the format, an exchange for it in `scripts/interop.py` and a CI job that runs it.
4. A library function and a command for every capability, tested to produce the same bytes.
5. A line in `doctor` that decodes one embedded vector of the format.

## Boundary files and reference tools

`src/anypatch/boundaries_test_support.py` generates files from fixed seeds at every edge a format has: the IPS 16 MiB wall and its `EOF` offset, record-length limits, 64 KiB GBA blocks, GDIFF command widths, VCDIFF windows, and a 40 MiB image whose CRC32 is forced to Paper Mario's so PMSR can be written. The content is random but known: each case's size and SHA-256 are pinned in `RECORDED`. `boundaries_test.py` writes every format for every case and checks the target comes back, and each refusal a format must make is declared in `REFUSED` with its message.

`scripts/interop.py` exchanges the same files with programs that read or write each format, in both directions: xdelta3, bsdiff and bspatch, bsdiff4, mendsley's bsdiff and bspatch for BSDIFF43, Flips, ApplyPPF and MakePPF, NINJA 2.0, javaxdelta and RomPatcher.js. Each CI interop job installs or builds one of them at a pinned version and runs it with `--tool`; the job in [ci.yml](.github/workflows/ci.yml) is the recipe for running the same tool locally. With every tool on the path:

```bash
PYTHONPATH=src ROMJS=<romjs checkout> ROMJS_HARNESS=<harness from ci.yml> \
  JAVAXDELTA=<javaxdelta.jar>:<trove.jar> NINJA="<php command from ci.yml>" \
  python scripts/interop.py --work <dir>
```

A failure caused by the other program is declared in `KNOWN` with the reason it was traced to. An entry that stops failing fails the run, so the table cannot go stale.

## Things this project will not accept

**No copied code.** A specification or another implementation is read to learn the format; the code here is written from that understanding. GPL sources are read only.

**No claim that has not been checked.** A change that asserts how a format behaves says how that was established, ideally by a reference patch from the program that defines the format.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/). semantic-release cuts each release from the commit history: `feat` gives a minor, `fix` a patch, and while the version is 0.x a breaking change gives a minor. The subject is at most 50 characters, starts lowercase and ends without a full stop; `.githooks/commit-msg` and CI both check it.

## Tests

Each test is three blocks, Arrange, Act and Assert, one call to the thing under test, and a name that states the behaviour. A bug fix ships with a test that fails without the fix.
