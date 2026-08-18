#!/usr/bin/env bash
# Run before `uvicorn` starts: wait for Postgres, then bring the global
# schema up to date. Tenant schemas are migrated by provisioning
# (`platform/service.py::create_tenant`), not by this script — see
# database-architecture.md §5.
set -euo pipefail

python -m vmss_api.backend_pre_start
alembic upgrade head
