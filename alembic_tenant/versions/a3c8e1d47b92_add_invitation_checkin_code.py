"""add invitations.checkin_code

Revision ID: a3c8e1d47b92
Revises: 9d2b6f1c4a8e
Create Date: 2026-10-14 00:00:00.000000

Numeric check-in code sent by SMS in place of a QR image
(openspec/changes/add-sms-numeric-checkin-code). Nullable: only approved
invitations whose primary contact prefers `sms` get one. Unique per tenant
schema; Postgres allows many NULLs under a unique index.

`op.add_column`/`op.create_index` don't honor `schema_translate_map`, so
`schema=` is passed explicitly (see d6cca1692557's note).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c8e1d47b92"
down_revision: str | None = "9d2b6f1c4a8e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    op.add_column(
        "invitations",
        sa.Column("checkin_code", sa.String(length=8), nullable=True),
        schema=schema,
    )
    op.create_index(
        "ix_invitations_checkin_code",
        "invitations",
        ["checkin_code"],
        unique=True,
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    op.drop_index("ix_invitations_checkin_code", table_name="invitations", schema=schema)
    op.drop_column("invitations", "checkin_code", schema=schema)
