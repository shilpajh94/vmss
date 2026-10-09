"""field group conditional visibility, and retiring the settings-based
group-visitor-count cap in favor of Visitor Info group's max_instances

Revision ID: c2f9a7d3e1b5
Revises: b8e3f4a1c6d2
Create Date: 2026-09-22 00:00:00.000000

Two independent additions to `b8e3f4a1c6d2`'s `form_field_groups` table:

1. `visibility_condition` (JSONB, nullable) — the same shape
   `form_fields.visibility_condition` already uses, letting a group be
   conditionally shown based on another field's value on the same step
   (`specs/form-builder/spec.md` "A Field Group May Declare Conditional
   Visibility"). Purely additive; every existing group gets `NULL` (always
   visible, unchanged behavior).

2. Backfill: the Visitor Info group's `max_instances` (currently `NULL`,
   meaning "unlimited" per `b8e3f4a1c6d2`'s seed) is set to
   `settings.invitation_max_group_visitors`'s *current* value, read once at
   migration-run time — a plain Python constant, no DB dependency. This
   keeps the group-registration visitor-count cap numerically identical
   immediately before and after this migration for every existing tenant,
   while `invitations/service.py` stops consulting the settings constant
   directly and instead reads this group's own `max_instances` through the
   same `validate_group_instance_count` path every other group already
   uses (`openspec/changes/add-repeatable-field-groups/design.md`, revised
   Decision 5). The setting itself (`core/config.py`) is not removed here —
   only its use as a live enforcement check is retired in application code.

`form_field_groups` is a table `b8e3f4a1c6d2` created, so `op.add_column`
here still needs `schema=` explicit (`275bc2310f49`'s documented gotcha —
`op.add_column` never resolves via `schema_translate_map` the way
`op.create_table` does, regardless of which migration created the table).

Hand-written, not `alembic revision --autogenerate` — same
`include_schemas=True` cross-schema-FK reflection limitation as every other
migration in this tree.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from vmss_api.core.config import settings

# revision identifiers, used by Alembic.
revision: str = "c2f9a7d3e1b5"
down_revision: str | None = "b8e3f4a1c6d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()

    op.add_column(
        "form_field_groups",
        sa.Column("visibility_condition", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=schema,
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            f'UPDATE "{schema}".form_field_groups '
            f"SET max_instances = :max_visitors "
            f"WHERE key = 'visitors' AND deleted_at IS NULL"
        ),
        {"max_visitors": settings.invitation_max_group_visitors},
    )


def downgrade() -> None:
    schema = _target_schema()
    op.drop_column("form_field_groups", "visibility_condition", schema=schema)
    # The `max_instances` backfill is not reversed: it was already `NULL`
    # (unlimited) before this migration, and restoring that would silently
    # re-widen a limit `invitations/service.py` may already depend on by
    # the time a downgrade runs. Leaving it set is the safer default; an
    # operator who needs the old unlimited behavior back can clear it
    # manually.
