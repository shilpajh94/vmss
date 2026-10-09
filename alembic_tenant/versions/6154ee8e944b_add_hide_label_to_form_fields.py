"""form builder: add hide_label to form_fields

Revision ID: 6154ee8e944b
Revises: 8c9072ca29f8
Create Date: 2026-09-24 00:00:00.000000

`hide_label` is a display-only property, the same shape as `width` — see
`openspec/changes/add-field-hide-label-option/design.md`. Defaults to
`false` on every existing row, matching today's always-visible-label
behavior.

`op.add_column` targets a table that already existed before this
migration, so it passes `schema=` explicitly (275bc2310f49's landmine —
`op.add_column` does not honor `schema_translate_map` the way
`op.create_table` does).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6154ee8e944b"
down_revision: str | None = "8c9072ca29f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    op.add_column(
        "form_fields",
        sa.Column("hide_label", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    op.drop_column("form_fields", "hide_label", schema=schema)
