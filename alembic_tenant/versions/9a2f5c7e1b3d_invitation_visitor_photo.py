"""invitation visitor photo

Revision ID: 9a2f5c7e1b3d
Revises: 2cabb55d1de8
Create Date: 2026-09-04 00:00:00.000001

`checkin-approval-workflow-improvements`: adds an optional profile-photo
storage key to the primary contact (`invitations.primary_contact_photo_
storage_key`) and to each co-visitor (`invitation_visitors.photo_storage_
key`), mirroring the existing ID-proof storage-key columns. Both nullable —
capturing a photo is never required. No backfill needed — every existing
row has no photo.

`invitations`/`invitation_visitors` already existed before this migration,
so `schema=` must be passed explicitly on every statement —
`op.add_column` does not pick up the connection's `schema_translate_map`
the way `op.create_table` does (same verified gotcha `a737ff0c6d62`'s and
`15d7580a57ed`'s docstrings document).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9a2f5c7e1b3d"
down_revision: str | None = "2cabb55d1de8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()

    op.add_column(
        "invitations",
        sa.Column("primary_contact_photo_storage_key", sa.String(500), nullable=True),
        schema=schema,
    )
    op.add_column(
        "invitation_visitors",
        sa.Column("photo_storage_key", sa.String(500), nullable=True),
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()

    op.drop_column("invitation_visitors", "photo_storage_key", schema=schema)
    op.drop_column("invitations", "primary_contact_photo_storage_key", schema=schema)
