"""functional index on digits-only primary_contact_phone

Revision ID: a7c3e1d9b5f2
Revises: 6791c5e6a421
Create Date: 2026-10-19 00:00:00.000000

Backs `GET /invitations/lookup-by-phone`
(`reception-phone-prefill-lookup/design.md`), which compares phones by
digits only. The expression must match
`invitations.repository.PHONE_DIGITS_SQL` exactly or Postgres won't use it.

`schema=` is passed explicitly: `create_index` on a pre-existing table
ignores `schema_translate_map`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c3e1d9b5f2"
down_revision: str | Sequence[str] | None = "6791c5e6a421"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX_NAME = "ix_invitations_primary_contact_phone_digits"


def upgrade() -> None:
    schema = op.get_context().version_table_schema
    op.create_index(
        _INDEX_NAME,
        "invitations",
        [sa.text(r"regexp_replace(primary_contact_phone, '\D', '', 'g')")],
        schema=schema,
        postgresql_where=sa.text("deleted_at IS NULL AND primary_contact_phone IS NOT NULL"),
    )


def downgrade() -> None:
    schema = op.get_context().version_table_schema
    op.drop_index(_INDEX_NAME, table_name="invitations", schema=schema)
