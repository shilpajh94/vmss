"""grant visitors:print_badge (admin, reception) and tenants:update (admin)

Revision ID: c4a8e1f7d093
Revises: e6944d5e8ee2
Create Date: 2026-11-02 00:00:00.000000

add-badge-print-flow: new permission codes. `seed_default_roles` only applies
catalog changes at provisioning or on a manual resync, so existing tenants
need this grant (same approach as `bff38dfa42e7`). Only the standard `admin`
and `reception` roles are touched; `host`, `security` and custom roles are
left alone. Idempotent; downgrade removes the grants and leaves the global
catalog rows.
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op
from vmss_api.core.config import settings

revision: str = "c4a8e1f7d093"
down_revision: str | Sequence[str] | None = "e6944d5e8ee2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GRANTS: dict[str, list[str]] = {
    "visitors:print_badge": ["admin", "reception"],
    "tenants:update": ["admin"],
}


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    global_schema = settings.global_schema_name
    conn = op.get_bind()
    for code, roles in _GRANTS.items():
        conn.execute(
            text(
                f'INSERT INTO "{global_schema}".permissions (id, code, description) '
                "VALUES (gen_random_uuid(), :code, :code) ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code},
        )
        for role in roles:
            conn.execute(
                text(
                    f'INSERT INTO "{schema}".role_permissions (role_id, permission_id) '
                    f'SELECT r.id, p.id FROM "{schema}".roles r '
                    f'CROSS JOIN "{global_schema}".permissions p '
                    "WHERE lower(r.name) = :role AND p.code = :code "
                    "ON CONFLICT DO NOTHING"
                ),
                {"code": code, "role": role},
            )


def downgrade() -> None:
    schema = _target_schema()
    global_schema = settings.global_schema_name
    conn = op.get_bind()
    for code, roles in _GRANTS.items():
        for role in roles:
            conn.execute(
                text(
                    f'DELETE FROM "{schema}".role_permissions WHERE role_id IN '
                    f'(SELECT id FROM "{schema}".roles WHERE lower(name) = :role) '
                    "AND permission_id IN "
                    f'(SELECT id FROM "{global_schema}".permissions WHERE code = :code)'
                ),
                {"code": code, "role": role},
            )
