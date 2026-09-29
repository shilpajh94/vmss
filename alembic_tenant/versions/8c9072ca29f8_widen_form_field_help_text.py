"""form builder: widen form_fields.help_text to 1000 characters

Revision ID: 8c9072ca29f8
Revises: c2f9a7d3e1b5
Create Date: 2026-09-23 00:00:00.000000

`static_text` fields store their rendered content in `help_text`
(`schemas.py::FormFieldCreate._check_static_text`); 500 characters was too
short for that use, so this raises the column (and the matching Pydantic
`max_length`) to 1000.

`op.alter_column` targets a table that already existed before this
migration, so it passes `schema=` explicitly (275bc2310f49's landmine —
`op.alter_column` does not honor `schema_translate_map` the way
`op.create_table` does).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c9072ca29f8"
down_revision: str | None = "c2f9a7d3e1b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    op.alter_column(
        "form_fields",
        "help_text",
        existing_type=sa.String(length=500),
        type_=sa.String(length=1000),
        existing_nullable=True,
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    op.alter_column(
        "form_fields",
        "help_text",
        existing_type=sa.String(length=1000),
        type_=sa.String(length=500),
        existing_nullable=True,
        schema=schema,
    )
