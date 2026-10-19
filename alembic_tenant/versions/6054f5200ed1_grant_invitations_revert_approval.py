"""grant invitations:revert-approval to the standard approving roles

Revision ID: 6054f5200ed1
Revises: bc9c5b3c20b6
Create Date: 2026-10-13 00:00:00.000000

`add-invitation-approval-revert` adds `invitations:revert-approval` to the
`admin`/`reception`/`host` catalog defaults (design.md Decision 6).
`seed_default_roles` only applies those at provisioning or on a manual
resync, so without this every existing tenant would get a 403 from the new
endpoint. Only those three standard roles are granted — `security` and
custom roles are left alone.

Idempotent: the catalog insert and the grant both skip existing rows.
Downgrade removes only this tenant's standard-role grants and leaves the
global catalog row, which other tenants still reference. Kept separate from
the column migration (`bc9c5b3c20b6`), same as `bff38dfa42e7`, so the grant
can be exercised on its own.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op
from vmss_api.core.config import settings

# revision identifiers, used by Alembic.
revision: str = "6054f5200ed1"
down_revision: str | Sequence[str] | None = "bc9c5b3c20b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REVERT = "invitations:revert-approval"
_GRANTED_ROLES = ["admin", "reception", "host"]


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
        {"code": _REVERT},
    )
    conn.execute(
        text(
            f'INSERT INTO "{schema}".role_permissions (role_id, permission_id) '
            f'SELECT r.id, p.id FROM "{schema}".roles r '
            f'CROSS JOIN "{global_schema}".permissions p '
            "WHERE lower(r.name) IN :roles AND p.code = :code "
            "ON CONFLICT DO NOTHING"
        ).bindparams(sa.bindparam("roles", expanding=True)),
        {"code": _REVERT, "roles": _GRANTED_ROLES},
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
        {"code": _REVERT, "roles": _GRANTED_ROLES},
    )
