#!/usr/bin/env bash
# Run before `uvicorn` starts: wait for Postgres, then bring the global
# schema up to date. Tenant schemas are migrated by provisioning
# (`platform/service.py::create_tenant`), not by this script — see
# database-architecture.md §5. The tenant-schema-drift check runs last (only
# once the global schema — and `tenant_schema_versions` with it — is
# guaranteed to exist) and only warns; it never blocks startup, since a
# lagging tenant doesn't mean the app itself can't come up.
set -euo pipefail

python -m vmss_api.backend_pre_start
alembic upgrade head
python -m vmss_api.backend_pre_start --check-tenant-drift
