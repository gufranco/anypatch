# Security

## Reporting

Report anything you believe is a security problem through [GitHub's private vulnerability reporting](https://github.com/gufranco/anypatch/security/advisories/new) on this repository, rather than in a public issue. There is no service behind this project and no user data, so the realistic reports are about the supply chain and about what a malformed patch can make the code do.

## What is in scope

| Class | Example |
|:--|:--|
| Malformed input | A crafted patch that makes anypatch write outside its output path, allocate without bound, loop forever, or execute anything |
| Wrong acceptance | A patch applied to a file its own checksum says it was not made for, or a conflict between two patches merged without a refusal |
| Supply chain | A pinned action, the Homebrew formula, or a release artefact that has been tampered with |

## What is not

anypatch reads files you already hold and writes files you asked for. It has no network access. A report that amounts to "this program can write a file" describes what it is for. The correctness of a third-party patch is outside what this project controls.

## Where this is distributed

This repository's releases page and the Homebrew formula in this repository, and nowhere else. anypatch is not published to PyPI; a package of that name anywhere else is not from this project.

## Supply chain

Every release carries a CycloneDX bill of materials and a Sigstore bundle over it. The bill is generated from an environment holding nothing but the package, and the release fails if anything else appears in it, because the library has no runtime dependencies and is meant to keep having none.
