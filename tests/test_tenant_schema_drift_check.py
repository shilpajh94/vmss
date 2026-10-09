"""`backend_pre_start.py::check_tenant_schema_drift` — see
`fix-tenant-migration-branch-drift/design.md`: a migration tree with more
than one head must be caught explicitly and logged at `ERROR` rather than
left to propagate as an unhandled exception, which `scripts/prestart.sh`'s
`set -euo pipefail` would turn into a startup-blocking crash — defeating
the point of this check being a non-blocking, warning-level drift report.
"""

import pytest

from vmss_api import backend_pre_start
from vmss_api.platform import service


async def test_check_tenant_schema_drift_does_not_raise_on_multiple_heads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _raise_ambiguous(db: object) -> list[object]:
        raise service.TenantMigrationHeadsAmbiguousError(["c1d8e5f9a2b3", "f1a2c7e9b3d5"])

    monkeypatch.setattr(service, "find_tenants_behind_head", _raise_ambiguous)

    await backend_pre_start.check_tenant_schema_drift()
