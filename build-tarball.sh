#!/usr/bin/env bash
# Build the deploy tarball, edge-integration-linux-<version>.tar.gz, from HEAD.
#
# git archive ships tracked files only, so untracked inventories, caches and
# agent files cannot reach a customer, and .gitattributes export-ignore drops
# the tracked development files. Uncommitted changes are not included.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

# The newest tag, else the short commit SHA, else a dev version outside git.
VERSION="$(git describe --tags --always 2>/dev/null || true)"
if [[ -z "${VERSION}" ]]; then
    VERSION="0.0.0-dev"
fi

ARTEFACT="edge-integration-linux-${VERSION}.tar.gz"

rm -f "./${ARTEFACT}"
git archive --format=tar.gz --prefix="edge-integration-linux-${VERSION}/" --output="./${ARTEFACT}" HEAD

echo "Built ./${ARTEFACT}" >&2
