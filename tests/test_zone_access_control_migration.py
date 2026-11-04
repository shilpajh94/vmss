"""Tenant migration `b9d4f1a6c3e8_zone_access_control` (add-zone-access-control):
its grant matrix must match the seeded role catalog, so a freshly provisioned
tenant and a migrated one end up with the same permissions. The create/drop
table half is exercised by running the real tenant migration chain (see the
change's tasks.md 2.3).
"""

import importlib.util
from pathlib import Path

from vmss_api.auth.rbac_catalog import PERMISSION_CODES, ROLE_PERMISSIONS

_MIGRATION = (
    Path(__file__).parents[1] / "alembic_tenant/versions/b9d4f1a6c3e8_zone_access_control.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("zone_access_control", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_grants_follow_the_default_role_matrix() -> None:
    grants = _load()._GRANTS
    assert grants["zones:manage"] == ["admin"]
    assert "security" in grants["access:scan"] and "reception" not in grants["access:scan"]
    assert set(grants["emergency:view"]) == {"admin", "reception", "security"}


async def test_migration_grants_match_the_seeded_catalog() -> None:
    for code, roles in _load()._GRANTS.items():
        assert code in PERMISSION_CODES
        for role in ROLE_PERMISSIONS:
            assert (code in ROLE_PERMISSIONS[role]) == (role in roles), (code, role)
