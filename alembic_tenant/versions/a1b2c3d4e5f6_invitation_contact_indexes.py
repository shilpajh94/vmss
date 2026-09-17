"""index invitations primary contact email/phone

Revision ID: a1b2c3d4e5f6
Revises: f74620cd4ffa
Create Date: 2026-09-17 00:00:00.000000

Adds indexes on `invitations.primary_contact_email` and
`invitations.primary_contact_phone` — the `visitor-return-visit` capability's
returning-visitor lookup (`openspec/changes/visitor-return-visit-login/`)
filters on these two columns to find a verified identifier's prior visits,
and neither carried an index before this (see design.md Decision 3 / tasks.md
2.2).

Hand-written, not `alembic revision --autogenerate` — same
`include_schemas=True` cross-schema-FK reflection limitation as every other
migration in this tree.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f74620cd4ffa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    op.create_index(
        op.f("ix_invitations_primary_contact_email"),
        "invitations",
        ["primary_contact_email"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        op.f("ix_invitations_primary_contact_phone"),
        "invitations",
        ["primary_contact_phone"],
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    op.drop_index(
        op.f("ix_invitations_primary_contact_phone"), table_name="invitations", schema=schema
    )
    op.drop_index(
        op.f("ix_invitations_primary_contact_email"), table_name="invitations", schema=schema
    )
