"""grant invitations:view-all to every non-host role holding invitations:view

Revision ID: d4e6f8a0b2c3
Revises: c3d5e7f9a1b2
Create Date: 2026-09-30 00:00:00.000000

`restrict-delegated-invitation-visibility` moves the branch-wide invitation
listing, the non-participant detail view and the admin dashboard from
`invitations:view` to the new `invitations:view-all`. `seed_default_roles`
backfills the standard roles, but never touches a custom role, so without
this a tenant's custom "manager" role would silently lose branch-wide access
(design.md Decision 4). `host` is excluded on purpose: it keeps
`invitations:view` (participant-only) and never gains `view-all`.

Idempotent: the catalog insert and the grants both skip existing rows.
Downgrade removes this tenant's `view-all` grants but leaves the global
catalog row, which other tenants may still reference.
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op
from vmss_api.core.config import settings

# revision identifiers, used by Alembic.
revision: str = "d4e6f8a0b2c3"
down_revision: str | Sequence[str] | None = "c3d5e7f9a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VIEW = "invitations:view"
_VIEW_ALL = "invitations:view-all"


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
        {"code": _VIEW_ALL},
    )
    conn.execute(
        text(
            f'INSERT INTO "{schema}".role_permissions (role_id, permission_id) '
            f'SELECT rp.role_id, va.id FROM "{schema}".role_permissions rp '
            f'JOIN "{global_schema}".permissions v ON v.id = rp.permission_id '
            f'JOIN "{schema}".roles r ON r.id = rp.role_id '
            f'CROSS JOIN "{global_schema}".permissions va '
            "WHERE v.code = :view AND va.code = :view_all AND lower(r.name) <> 'host' "
            "ON CONFLICT DO NOTHING"
        ),
        {"view": _VIEW, "view_all": _VIEW_ALL},
    )


def downgrade() -> None:
    schema = _target_schema()
    global_schema = settings.global_schema_name
    op.get_bind().execute(
        text(
            f'DELETE FROM "{schema}".role_permissions WHERE permission_id IN '
            f'(SELECT id FROM "{global_schema}".permissions WHERE code = :view_all)'
        ),
        {"view_all": _VIEW_ALL},
    )
