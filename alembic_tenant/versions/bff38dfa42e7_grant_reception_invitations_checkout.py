"""grant invitations:checkout to the standard reception role

Revision ID: bff38dfa42e7
Revises: a7c3e9f1b2d4
Create Date: 2026-10-13 00:00:00.000000

`grant-reception-checkout-permission` adds `invitations:checkout` to
Reception's catalog defaults so front office can check a visitor out from
the board. `seed_default_roles` only applies that at provisioning or on a
manual resync, so without this every existing tenant's receptionists would
see the web Check Out button and get a 403 (design.md Decision 1). Only the
standard `reception` role is granted — `host` and custom roles are left
alone (Decision 2).

Idempotent: the catalog insert and the grant both skip existing rows.
Downgrade removes only this tenant's reception grant and leaves the global
catalog row, which `admin`/`security` and other tenants still reference.
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op
from vmss_api.core.config import settings

# revision identifiers, used by Alembic.
revision: str = "bff38dfa42e7"
down_revision: str | Sequence[str] | None = "a7c3e9f1b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHECKOUT = "invitations:checkout"


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
        {"code": _CHECKOUT},
    )
    conn.execute(
        text(
            f'INSERT INTO "{schema}".role_permissions (role_id, permission_id) '
            f'SELECT r.id, p.id FROM "{schema}".roles r '
            f'CROSS JOIN "{global_schema}".permissions p '
            "WHERE lower(r.name) = 'reception' AND p.code = :code "
            "ON CONFLICT DO NOTHING"
        ),
        {"code": _CHECKOUT},
    )


def downgrade() -> None:
    schema = _target_schema()
    global_schema = settings.global_schema_name
    op.get_bind().execute(
        text(
            f'DELETE FROM "{schema}".role_permissions WHERE role_id IN '
            f"(SELECT id FROM \"{schema}\".roles WHERE lower(name) = 'reception') "
            "AND permission_id IN "
            f'(SELECT id FROM "{global_schema}".permissions WHERE code = :code)'
        ),
        {"code": _CHECKOUT},
    )
