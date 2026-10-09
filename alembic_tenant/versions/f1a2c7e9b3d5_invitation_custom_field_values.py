"""invitation/visitor/vehicle custom_field_values columns

Revision ID: f1a2c7e9b3d5
Revises: 762e2a7cf5d1
Create Date: 2026-09-16 00:00:00.000000

Adds `custom_field_values` (JSONB, per-row map keyed by field key) to
`invitations`, `invitation_visitors`, and `invitation_vehicles`, plus
`primary_contact_custom_field_values` on `invitations` — the storage for
admin-authored fields' submitted answers
(`add-generic-custom-field-support/design.md` Decision 1). Every step now
accepts new admin-authored fields (`form_builder.service.create_field`'s
`_FIXED_FIELD_SET_STEP_KEYS` guard is removed in the same change), and this
is where their answers land: `invitations.custom_field_values` for
Visit Details/Carried Items/Consent Agreement/custom-step fields (one map
per invitation), `invitations.primary_contact_custom_field_values` for the
primary contact's own Visitor Info answers (kept separate from the above so
the two scopes never share a key namespace on one row),
`invitation_visitors.custom_field_values` for each co-visitor's own Visitor
Info answers, and `invitation_vehicles.custom_field_values` for each
vehicle's own Vehicle Info answers.

Purely additive: nullable-equivalent (`server_default '{}'::jsonb`,
`nullable=False`), no backfill needed for existing rows.

All four are new columns on pre-existing tables, so — per
`275bc2310f49`'s documented gotcha — `op.add_column` passes `schema=`
explicitly; the connection's `schema_translate_map` alone does not resolve
it the way `op.create_table` does.

Hand-written, not `alembic revision --autogenerate` — same
`include_schemas=True` cross-schema-FK reflection limitation as every other
migration in this tree.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2c7e9b3d5"
down_revision: str | None = "762e2a7cf5d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def _custom_field_values_column() -> sa.Column:
    return sa.Column(
        "custom_field_values",
        postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )


def upgrade() -> None:
    schema = _target_schema()
    op.add_column("invitations", _custom_field_values_column(), schema=schema)
    op.add_column(
        "invitations",
        sa.Column(
            "primary_contact_custom_field_values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema=schema,
    )
    op.add_column("invitation_visitors", _custom_field_values_column(), schema=schema)
    op.add_column("invitation_vehicles", _custom_field_values_column(), schema=schema)


def downgrade() -> None:
    schema = _target_schema()
    op.drop_column("invitation_vehicles", "custom_field_values", schema=schema)
    op.drop_column("invitation_visitors", "custom_field_values", schema=schema)
    op.drop_column("invitations", "primary_contact_custom_field_values", schema=schema)
    op.drop_column("invitations", "custom_field_values", schema=schema)
