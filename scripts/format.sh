#!/usr/bin/env bash
# Auto-fixes what ruff can fix; leaves the rest for `scripts/lint.sh` to catch.
set -euo pipefail

ruff check --fix .
ruff format .
