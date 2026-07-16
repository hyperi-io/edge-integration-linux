#!/usr/bin/env bash
#
# Build the collector-endpoint-linux deployment tarball.
#
# Version is derived from the latest git tag. This repo was migrated without
# its tags, so fall back to a dev version when none exist -- otherwise the
# artefact name is left dangling (e.g. "...-.tar.gz"). The rm and tar targets
# use one shared name so the previous artefact is actually removed.
set -euo pipefail

VERSION="$(git tag --sort=version:refname 2>/dev/null | tail -1 || true)"
if [[ -z "${VERSION}" ]]; then
    VERSION="0.0.0-dev"
fi

ARTEFACT="hypersec-collector-endpoint-linux-${VERSION}.tar.gz"

rm -f "./${ARTEFACT}"
tar --exclude="./deploy" \
    --exclude="./build-tarball.sh" \
    --exclude="./environments/hs*" \
    --exclude="./.git" \
    --exclude="./.gitattributes" \
    --exclude="./*.tar.gz" \
    -zcvf "./${ARTEFACT}" .
