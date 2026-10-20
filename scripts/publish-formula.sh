#!/usr/bin/env bash

set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "${root}"

bot_name=${FORMULA_BOT_NAME:?bot name required}
bot_email=${FORMULA_BOT_EMAIL:?bot email required}
: "${GITHUB_TOKEN:?token required}"
repository=${GITHUB_REPOSITORY:?repository required}
remote=${FORMULA_REMOTE:-https://github.com/${repository}.git}

readonly CREDENTIAL_KEY="credential.https://github.com.helper"
# shellcheck disable=SC2016
readonly CREDENTIAL_HELPER='!f(){ echo username=x-access-token; echo "password=${GITHUB_TOKEN}"; }; f'

git fetch --tags --quiet origin
tag=$(git tag --list --sort=-v:refname 'v*' | head -1)
if [[ -z ${tag} ]]; then
  printf 'no tag exists yet, nothing to point the formula at\n'
  exit 0
fi

bash scripts/update-formula.sh "${tag}"

if git diff --quiet Formula/anypatch.rb; then
  printf 'the formula already points at %s\n' "${tag}"
  exit 0
fi

git remote set-url origin "${remote}"
git add Formula/anypatch.rb
git -c "user.name=${bot_name}" -c "user.email=${bot_email}" \
  commit --quiet -m "chore(formula): point at ${tag} [skip ci]"
git \
  -c "${CREDENTIAL_KEY}=" \
  -c "${CREDENTIAL_KEY}=${CREDENTIAL_HELPER}" \
  push --quiet origin HEAD:main

printf 'formula published for %s\n' "${tag}"
