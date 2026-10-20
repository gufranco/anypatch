## What this changes

One paragraph: what a reader of the diff would not work out on their own.

## How it was established

For a format change, the reference patch it was checked against and the program or specification that produced it.

## Checklist

- [ ] `uv run ruff format --check .` and `uv run ruff check .` pass
- [ ] `uv run mypy` passes
- [ ] `uv run pytest --cov` passes at 100% on a clean checkout
- [ ] A new capability works both as a library call and as a command
- [ ] A new format names its source in NOTICE.md and has reference patches from another program or its specification
