#!/usr/bin/env bash
#
# Build the collector-endpoint-linux deployment tarball.
#
# Version comes from `git describe`: the newest tag when the repo is tagged,
# otherwise the short commit SHA -- so every artefact is traceable to a commit
# rather than a fixed placeholder. One shared ARTEFACT name drives both the rm
# and the archive, so the previous artefact is actually removed.
#
# The archive is built with `git archive`, NOT tar-from-".". That choice is
# deliberate and worth keeping:
#
#   * It ships TRACKED FILES ONLY. A denylist ships anything it forgets to name,
#     and it cannot name what does not exist yet -- .ansible/ leaked exactly that
#     way (ansible creates it on the first local run; tar does not read
#     .gitignore; git stays quiet while its subdirs are empty). Working-tree
#     clutter, agent artefacts (.hyperi-ai, .claude), caches (.ansible, .venv,
#     __pycache__) and a stray environments/<customer> inventory with real
#     hostnames or a password now CANNOT reach a customer, because none of them
#     are in the commit.
#   * Tracked-but-internal paths are excluded via export-ignore in .gitattributes
#     -- see that file. That is the only list to maintain, and it only covers
#     things we deliberately committed.
#   * It reads from the object store, so it never trips over writing the artefact
#     into the directory being archived (the old tar-from-"." always exited 1:
#     "file changed as we read it", which set -euo pipefail turned into a failed
#     build).
#
# Consequence worth knowing: the artefact is built from HEAD, so uncommitted
# working-tree changes are NOT included. That is deliberate -- a release artefact
# should reflect committed state.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

# --tags matches lightweight tags too; --always falls back to a short SHA when
# no tag is reachable yet. The outer fallback covers building from an unpacked
# source tree that has no .git at all.
VERSION="$(git describe --tags --always 2>/dev/null || true)"
if [[ -z "${VERSION}" ]]; then
    VERSION="0.0.0-dev"
fi

ARTEFACT="hyperi-collector-endpoint-linux-${VERSION}.tar.gz"

rm -f "./${ARTEFACT}"
git archive --format=tar.gz --output="./${ARTEFACT}" HEAD

echo "Built ./${ARTEFACT}" >&2
