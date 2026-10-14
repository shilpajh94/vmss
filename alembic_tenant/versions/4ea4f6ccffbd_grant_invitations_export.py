"""grant invitations:export to the standard branch-wide viewing roles

Revision ID: 4ea4f6ccffbd
Revises: 6054f5200ed1
Create Date: 2026-10-13 00:00:00.000000

`add-invitation-export` adds `invitations:export` to the `admin`/
`reception`/`security` catalog defaults — the roles that already hold
`invitations:view-all` (design.md Decision 6). `seed_default_roles` only
applies those at provisioning or on a manual resync, so without this every
existing tenant would get a 403 from `GET /invitations/export`. `host` and
custom roles are left alone.

Idempotent: the catalog insert and the grant both skip existing rows.
Downgrade removes only this tenant's standard-role grants and leaves the
global catalog row, which other tenants still reference.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op
from vmss_api.core.config import settings

# revision identifiers, used by Alembic.
revision: str = "4ea4f6ccffbd"
down_revision: str | Sequence[str] | None = "6054f5200ed1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EXPORT = "invitations:export"
_GRANTED_ROLES = ["admin", "reception", "security"]


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
        {"code": _EXPORT},
    )
    conn.execute(
        text(
            f'INSERT INTO "{schema}".role_permissions (role_id, permission_id) '
            f'SELECT r.id, p.id FROM "{schema}".roles r '
            f'CROSS JOIN "{global_schema}".permissions p '
            "WHERE lower(r.name) IN :roles AND p.code = :code "
            "ON CONFLICT DO NOTHING"
        ).bindparams(sa.bindparam("roles", expanding=True)),
        {"code": _EXPORT, "roles": _GRANTED_ROLES},
    )


def downgrade() -> None:
    schema = _target_schema()
    global_schema = settings.global_schema_name
    op.get_bind().execute(
        text(
            f'DELETE FROM "{schema}".role_permissions WHERE role_id IN '
            f'(SELECT id FROM "{schema}".roles WHERE lower(name) IN :roles) '
            "AND permission_id IN "
            f'(SELECT id FROM "{global_schema}".permissions WHERE code = :code)'
        ).bindparams(sa.bindparam("roles", expanding=True)),
        {"code": _EXPORT, "roles": _GRANTED_ROLES},
    )
