#!/usr/bin/env bash
# Run the Docker test harness. Needs docker and uv. Arguments go to pytest:
#
#   ./run.sh                          # whole matrix
#   ./run.sh -m 'not eol'             # current distros only
#   ./run.sh -k rocky                 # a subset
#   ./run.sh 'test_forwarding.py::test_audit_forwarding[ubuntu-24.04]'
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

uv sync --locked
# --no-cache: ansible-galaxy caches an empty entry before each request, so a
# retried server error becomes a fatal "Missing expected 'results'".
uv run --locked ansible-galaxy collection install -r requirements.yml -p ./collections --force --no-cache
exec uv run --locked pytest "$@"
