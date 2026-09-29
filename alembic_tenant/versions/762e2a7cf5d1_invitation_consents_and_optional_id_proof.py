"""invitation consents column, optional co-visitor id proof

Revision ID: 762e2a7cf5d1
Revises: afb2544db111
Create Date: 2026-09-15 00:00:00.000000

Adds `invitations.consents` (JSONB, one row's worth of branch-configured
consent-key -> accepted-bool pairs) alongside the three pre-existing fixed
consent booleans, which `create_invitation` stops writing to as of this
change (kept for one release's burn-in — `openspec/changes/form-builder/
design.md` Migration Plan step 6 drops them in a follow-up migration, not
this one). Also relaxes `invitation_visitors.id_proof_type`/
`id_proof_storage_key` to nullable: whether a co-visitor's ID proof is
captured at all is now branch-configurable
(specs/form-builder/spec.md "System Fields Are Seeded..."), not
unconditionally mandatory. `invitations.primary_contact_id_proof_type`/
`_storage_key` need no such change — both were already nullable.

Both alterations target pre-existing tables, so — per 275bc2310f49's
documented gotcha — `op.add_column`/`op.alter_column` pass `schema=`
explicitly; the connection's `schema_translate_map` alone does not resolve
them the way `op.create_table` does.

Hand-written, not `alembic revision --autogenerate` — same
`include_schemas=True` cross-schema-FK reflection limitation as every other
migration in this tree.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "762e2a7cf5d1"
down_revision: str | None = "afb2544db111"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    op.add_column(
        "invitations",
        sa.Column(
            "consents",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema=schema,
    )
    op.alter_column(
        "invitation_visitors",
        "id_proof_type",
        existing_type=sa.String(length=50),
        nullable=True,
        schema=schema,
    )
    op.alter_column(
        "invitation_visitors",
        "id_proof_storage_key",
        existing_type=sa.String(length=500),
        nullable=True,
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    op.alter_column(
        "invitation_visitors",
        "id_proof_storage_key",
        existing_type=sa.String(length=500),
        nullable=False,
        schema=schema,
    )
    op.alter_column(
        "invitation_visitors",
        "id_proof_type",
        existing_type=sa.String(length=50),
        nullable=False,
        schema=schema,
    )
    op.drop_column("invitations", "consents", schema=schema)
