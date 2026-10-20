# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [semantic versioning](https://semver.org/spec/v2.0.0.html). Release notes for each tag are on the [releases page](https://github.com/gufranco/anypatch/releases).

## Unreleased

### What's new

- Read IPS, IPS32, EBP, ZPS, APS for N64 and GBA, UPS, BPS, PPF 1.0 to 3.0, RUP, PMSR with or without Yay0, BDF and xdelta, and write all of them except APS for GBA and PMSR. The format code moved here from n64-save-patches with its history.
- `anypatch make`, `apply`, `merge`, `convert`, `info` and `formats`, each the same as the function of that name in `anypatch.api`.
- Applying several patches compares what each changes on the clean source and refuses any two that write different bytes to one place, listing every range.
- `doctor` writes and replays a patch in every writable format and decodes the two read-only ones.

## 0.1.0

### What's new

- `anypatch doctor` and `anypatch.doctor.diagnose()` report the version, Python, platform and the standard library codecs the formats use, as text or as JSON.
- Installable with Homebrew from this repository, and usable as a library with no dependency outside the standard library.
