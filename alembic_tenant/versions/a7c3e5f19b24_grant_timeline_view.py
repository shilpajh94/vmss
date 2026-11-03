"""grant timeline:view (admin, reception, security)

Revision ID: a7c3e5f19b24
Revises: e2a3b4c5d6f7
Create Date: 2026-11-03 00:00:00.000000

add-visit-timeline: new permission code. `seed_default_roles` only applies
catalog changes at provisioning or on a manual resync, so existing tenants
need this grant (same approach as `c4a8e1f7d093`). Only the standard `admin`,
`reception` and `security` roles are touched. Idempotent; downgrade removes
the grants and leaves the global catalog row.
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op
from vmss_api.core.config import settings

revision: str = "a7c3e5f19b24"
down_revision: str | Sequence[str] | None = "e2a3b4c5d6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CODE = "timeline:view"
_ROLES = ["admin", "reception", "security"]


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    global_schema = settings.global_schema_name
    conn = op.get_bind()
    conn.execute(
        text(
            f'INSERT INTO "{global_schema}".permissions (id, code, description) '
            "VALUES (gen_random_uuid(), :code, :code) ON CONFLICT (code) DO NOTHING"
        ),
        {"code": _CODE},
    )
    for role in _ROLES:
        conn.execute(
            text(
                f'INSERT INTO "{schema}".role_permissions (role_id, permission_id) '
                f'SELECT r.id, p.id FROM "{schema}".roles r '
                f'CROSS JOIN "{global_schema}".permissions p '
                "WHERE lower(r.name) = :role AND p.code = :code "
                "ON CONFLICT DO NOTHING"
            ),
            {"code": _CODE, "role": role},
        )


def downgrade() -> None:
    schema = _target_schema()
    global_schema = settings.global_schema_name
    conn = op.get_bind()
    for role in _ROLES:
        conn.execute(
            text(
                f'DELETE FROM "{schema}".role_permissions WHERE role_id IN '
                f'(SELECT id FROM "{schema}".roles WHERE lower(name) = :role) '
                "AND permission_id IN "
                f'(SELECT id FROM "{global_schema}".permissions WHERE code = :code)'
            ),
            {"code": _CODE, "role": role},
        )
