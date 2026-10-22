# Working in this repository

[README.md](README.md) is the document written for a person, and it is the source of truth for everything public: what each command does, how to install it, and what the library exposes. The Japanese, Simplified Chinese and Hong Kong Traditional Chinese READMEs are the same document translated. Change the English one first, then each translation, then anything derived from them: the package description, the formula `desc`, the citation abstract and the GitHub About text. `tests/repository/test_public_text.py` fails when a copy drifts.

## What this project is

One library and one command line over the same code, for binary patches in every format that has a public specification or an open reference implementation. The command line decides nothing: every command parses its arguments, calls the library function of the same capability, and prints what came back. The library imports nothing outside the Python standard library; Typer is the `cli` extra.

## Legal and shareable, a hard rule

This project is for preservation and interoperability, and it must stay safe to share in public. These points are not negotiable, and a change that breaks one is wrong even when everything else passes.

- No ROM, BIOS, save image, or patch bytes are ever committed, in any format, as a fixture or in any other guise. Development images are supplied by the developer, held legally, and kept out of git. Reference material used while learning a format clean-room is used legally and never versioned.
- No link or pointer to where to obtain a ROM, a save, or a patch is committed.
- No vocabulary that frames the work as unlawful copying or as defeating a protection appears in any tracked file. The exact terms live in [tests/repository/test_legal_hygiene.py](tests/repository/test_legal_hygiene.py), which scans every tracked file and fails the build on a match, and also fails if a ROM, BIOS, save, or patch file extension is ever tracked.
- Formats are learned clean-room from a public specification or an open implementation; GPL sources are read only; [NOTICE.md](NOTICE.md) names each, and no code is copied.
- The suite that gates every change, `uv run pytest`, runs on synthetic data alone and contacts no external site. The optional interop jobs exchange patches with reference tools pinned by checksum on reputable code hosts; no reference tool is fetched from a personal third-party site.
- A reference tool that is distributed only from a personal third-party site is never fetched or built by this project. It is declared in [artifacts.manifest.json](artifacts.manifest.json) by name and by several independent digests, SHA-256, SHA-1, MD5, and CRC32, plus its size in bytes, and the developer supplies it, legally obtained, in the gitignored `external/` folder. Several digests are recorded together rather than one, because a single digest can be searched to locate the file online; the manifest identifies the file without pointing at any source, and no download location is ever recorded.

## Rules that are invisible in the code

- Never publish to PyPI. Distribution is this repository's releases and the formula in the shared tap `gufranco/homebrew-tap`.
- Every format is tested against reference patches from another program or from its specification, stored as data. A format with neither is not supported, and the README says why.
- A patch whose format carries a checksum of its source is refused on any other file, naming the format and both values. Two patches that write different bytes to one offset are refused together, listing every range. Nothing is written after a refusal.
- No code is copied from a reference. GPL sources are read only. [NOTICE.md](NOTICE.md) names every source and its license.

## The gates

Every change passes all of these. A gate that was not run is a gate that failed.

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest --cov
pnpm run format:check
```

Coverage is 100% of statements and branches. Tests carry only the `# Arrange`, `# Act` and `# Assert` markers: three blocks, one call to the thing under test, and a name that states the behaviour.

## Where things live

| Path | Holds |
|:--|:--|
| `src/anypatch/` | The library; each module's tests sit beside it as `<module>_test.py` |
| `src/anypatch/cli/` | The Typer command line |
| `src/anypatch/entry.py` | The console script, which says how to get the `cli` extra when Typer is absent |
| `tests/` | Tests of the repository itself and of `python -m anypatch` |
| `scripts/` | Release and commit-message scripts |
