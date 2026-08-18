#!/usr/bin/env bash
# Lint gate — see git-workflow.md §3/§4 (PR checklist / CI gate).
set -euo pipefail

ruff check .
ruff format --check .
mypy src
