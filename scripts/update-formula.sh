#!/usr/bin/env bash

set -euo pipefail

tag=${1:?tag required}
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
formula="${root}/Formula/anypatch.rb"
base=${ANYPATCH_ARCHIVE_BASE:-https://github.com/gufranco/anypatch/archive/refs/tags}
url="${base}/${tag}.tar.gz"

work=$(mktemp -d "${TMPDIR:-/tmp}/anypatch-formula-XXXXXX")
trap 'rm -rf "${work}"' EXIT

if ! curl -fsSL --retry 5 --retry-all-errors "${url}" -o "${work}/source.tar.gz" 2>/dev/null; then
  printf 'could not download %s\n' "${url}" >&2
  exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
  checksum=$(sha256sum "${work}/source.tar.gz" | awk '{print $1}')
else
  checksum=$(shasum -a 256 "${work}/source.tar.gz" | awk '{print $1}')
fi

tar -xzf "${work}/source.tar.gz" -C "${work}"
version_file=$(find "${work}" -path '*/src/anypatch/version.py' | head -1)
if [[ -z ${version_file} ]]; then
  printf 'the release archive has no src/anypatch/version.py\n' >&2
  exit 1
fi
packaged_version=$(sed -n 's/^VERSION = "\(.*\)"$/\1/p' "${version_file}")
if [[ ${packaged_version} != "${tag#v}" ]]; then
  printf 'the release is tagged %s but the code in it says %s\n' "${tag}" "${packaged_version}" >&2
  printf 'set the version, tag again, and publish again\n' >&2
  exit 1
fi

python3 - "${formula}" "${url}" "${checksum}" <<'PY'
import re
import sys
from pathlib import Path

path, url, checksum = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
text = path.read_text()
text = re.sub(r'url "[^"]+"', f'url "{url}"', text, count=1)
text = re.sub(r'sha256 "[0-9a-f]{64}"', f'sha256 "{checksum}"', text, count=1)
path.write_text(text)
PY

printf 'formula now points at %s\n' "${tag}"
printf '  url:    %s\n' "${url}"
printf '  sha256: %s\n' "${checksum}"
