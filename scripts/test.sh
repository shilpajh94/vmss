#!/usr/bin/env bash
# Full test suite against real Postgres — see testing-standards.md.
set -euo pipefail

pytest --cov=vmss_api --cov-report=term-missing "$@"
