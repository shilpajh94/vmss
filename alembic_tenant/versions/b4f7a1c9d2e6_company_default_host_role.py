"""company default host role

Revision ID: b4f7a1c9d2e6
Revises: 9a2f5c7e1b3d
Create Date: 2026-09-07 00:00:00.000001

`role-based-invitation-workflow`: adds `companies.default_host_role_id`, a
nullable FK to `roles.id` naming which Role a newly submitted invitation's
`stepOrder` 0 ownership step is created for. Null means "use the tenant's
standard `reception` role" — every resolver falls back to that, so no
backfill is needed for existing rows.

`companies`/`roles` already existed before this migration, so `schema=` must
be passed explicitly on every statement — `op.add_column` does not pick up
the connection's `schema_translate_map` the way `op.create_table` does (same
verified gotcha `9a2f5c7e1b3d`'s docstring documents).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4f7a1c9d2e6"
down_revision: str | None = "9a2f5c7e1b3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()

    op.add_column(
        "companies",
        sa.Column("default_host_role_id", sa.Uuid(), nullable=True),
        schema=schema,
    )
    op.create_foreign_key(
        "fk_companies_default_host_role_id_roles",
        "companies",
        "roles",
        ["default_host_role_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()

    op.drop_constraint(
        "fk_companies_default_host_role_id_roles",
        "companies",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_column("companies", "default_host_role_id", schema=schema)
