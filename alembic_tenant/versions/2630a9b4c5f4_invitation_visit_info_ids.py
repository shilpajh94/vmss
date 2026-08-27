"""invitations: optional purpose_id/host_id/duration_id/department_id

Revision ID: 2630a9b4c5f4
Revises: 09a7eeb963d3
Create Date: 2026-08-24 00:00:02.000000

visit-info-lookup-api: four new nullable FK columns on `invitations`,
alongside the existing free-text `purpose_of_visit`/`host_name_or_email`/
`expected_duration`/`department_to_visit` string columns. Purely additive —
no existing row or reader is affected; see
openspec/changes/visit-info-lookup-api/design.md.

Every `op.add_column`/`op.create_foreign_key`/`op.drop_constraint`/
`op.drop_column` below passes `schema=_target_schema()` explicitly —
verified gotcha (see `c3d8f21a9b6e`, `275bc2310f49`): unlike
`op.create_table`, these do NOT pick up the connection's
`schema_translate_map` on their own.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2630a9b4c5f4"
down_revision: str | None = "09a7eeb963d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()

    op.add_column(
        "invitations", sa.Column("purpose_id", sa.Uuid(), nullable=True), schema=schema
    )
    op.create_foreign_key(
        "fk_invitations_purpose_id_visit_purposes",
        "invitations",
        "visit_purposes",
        ["purpose_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_index(
        op.f("ix_invitations_purpose_id"), "invitations", ["purpose_id"], unique=False, schema=schema
    )

    op.add_column("invitations", sa.Column("host_id", sa.Uuid(), nullable=True), schema=schema)
    op.create_foreign_key(
        "fk_invitations_host_id_users",
        "invitations",
        "users",
        ["host_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_index(
        op.f("ix_invitations_host_id"), "invitations", ["host_id"], unique=False, schema=schema
    )

    op.add_column(
        "invitations", sa.Column("duration_id", sa.Uuid(), nullable=True), schema=schema
    )
    op.create_foreign_key(
        "fk_invitations_duration_id_visit_durations",
        "invitations",
        "visit_durations",
        ["duration_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_index(
        op.f("ix_invitations_duration_id"),
        "invitations",
        ["duration_id"],
        unique=False,
        schema=schema,
    )

    op.add_column(
        "invitations", sa.Column("department_id", sa.Uuid(), nullable=True), schema=schema
    )
    op.create_foreign_key(
        "fk_invitations_department_id_departments",
        "invitations",
        "departments",
        ["department_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_index(
        op.f("ix_invitations_department_id"),
        "invitations",
        ["department_id"],
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()

    op.drop_index(op.f("ix_invitations_department_id"), "invitations", schema=schema)
    op.drop_constraint(
        "fk_invitations_department_id_departments", "invitations", schema=schema, type_="foreignkey"
    )
    op.drop_column("invitations", "department_id", schema=schema)

    op.drop_index(op.f("ix_invitations_duration_id"), "invitations", schema=schema)
    op.drop_constraint(
        "fk_invitations_duration_id_visit_durations",
        "invitations",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_column("invitations", "duration_id", schema=schema)

    op.drop_index(op.f("ix_invitations_host_id"), "invitations", schema=schema)
    op.drop_constraint(
        "fk_invitations_host_id_users", "invitations", schema=schema, type_="foreignkey"
    )
    op.drop_column("invitations", "host_id", schema=schema)

    op.drop_index(op.f("ix_invitations_purpose_id"), "invitations", schema=schema)
    op.drop_constraint(
        "fk_invitations_purpose_id_visit_purposes",
        "invitations",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_column("invitations", "purpose_id", schema=schema)
