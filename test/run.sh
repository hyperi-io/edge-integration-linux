#!/usr/bin/env bash
# HyperI Linux audit collector - docker test harness runner.
#
# Portable: needs only `docker` and `uv`. Runs the distro matrix in
# matrix.yml. amd64-only targets (el6) auto-SKIP on an arm64 host and run
# natively on an x64 host - so on your x64 Ubuntu box this runs the full
# matrix, on an arm64 Mac it runs the arm64-native subset + proves the skip.
#
#   ./run.sh                          # whole matrix
#   ./run.sh -k rocky                 # a subset (pytest -k expression)
#   ./run.sh 'test_forwarding.py::test_audit_forwarding[ubuntu-24.04]'
#   ./run.sh -m 'not eol'             # current distros only (skip EOL bucket)
set -euo pipefail
cd "$(dirname "$0")"

uv sync
uv run ansible-galaxy collection install -r requirements.yml -p ./collections --force
exec uv run pytest "$@"
