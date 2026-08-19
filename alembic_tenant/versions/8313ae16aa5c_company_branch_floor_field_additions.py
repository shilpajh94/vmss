"""org structure: company, branch, and floor field additions

Revision ID: 8313ae16aa5c
Revises: c3d8f21a9b6e
Create Date: 2026-08-19 00:00:00.000000

Fills field gaps a design-vs-implementation review of the admin portal
surfaced (see
openspec/changes/add-role-management-and-org-field-gaps/proposal.md):
tenant-wide visitor-policy defaults on `Company` ("Organisation Configs"
screen), the branch profile fields on `Branch` (location, contact,
operating hours, notes), and capacity/access-level fields on `Floor`.
`Building.is_active` needed no migration — the column already existed, only
`BuildingCreate` gained the ability to set it (an application-layer change).

All new columns are nullable (or boolean with a default), so this is a pure
additive migration — no backfill needed.

Hand-written, not `alembic revision --autogenerate` — same
`include_schemas=True` limitation as every migration in this tree (see
275bc2310f49's docstring). Every `add_column`/`create_foreign_key` below
targets a table that already existed before this migration, so — per the
landmine documented in 275bc2310f49 — each passes `schema=` explicitly
rather than relying on the connection's `schema_translate_map`, which
`op.add_column`/`op.drop_column` (and friends used alongside them) do not
honor the way `op.create_table` does.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8313ae16aa5c"
down_revision: str | None = "c3d8f21a9b6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()

    op.add_column(
        "companies",
        sa.Column("default_timezone", sa.String(length=50), nullable=True),
        schema=schema,
    )
    op.add_column(
        "companies",
        sa.Column(
            "auto_approve_pre_registered_visitors",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        schema=schema,
    )
    op.add_column(
        "companies",
        sa.Column("badge_expiry_duration_minutes", sa.Integer(), nullable=True),
        schema=schema,
    )

    op.add_column("branches", sa.Column("city", sa.String(length=100), nullable=True), schema=schema)
    op.add_column(
        "branches", sa.Column("country", sa.String(length=100), nullable=True), schema=schema
    )
    op.add_column(
        "branches", sa.Column("contact_person_user_id", sa.Uuid(), nullable=True), schema=schema
    )
    op.add_column(
        "branches", sa.Column("contact_email", sa.String(length=255), nullable=True), schema=schema
    )
    op.add_column(
        "branches", sa.Column("contact_phone", sa.String(length=50), nullable=True), schema=schema
    )
    op.add_column(
        "branches",
        sa.Column("operating_hours_from", sa.String(length=10), nullable=True),
        schema=schema,
    )
    op.add_column(
        "branches",
        sa.Column("operating_hours_to", sa.String(length=10), nullable=True),
        schema=schema,
    )
    op.add_column(
        "branches", sa.Column("notes", sa.String(length=2000), nullable=True), schema=schema
    )
    op.create_foreign_key(
        "fk_branches_contact_person_user_id",
        "branches",
        "users",
        ["contact_person_user_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )

    op.add_column("floors", sa.Column("capacity", sa.Integer(), nullable=True), schema=schema)
    op.add_column(
        "floors", sa.Column("capacity_type", sa.String(length=20), nullable=True), schema=schema
    )
    op.add_column(
        "floors", sa.Column("access_level", sa.String(length=20), nullable=True), schema=schema
    )


def downgrade() -> None:
    schema = _target_schema()

    op.drop_column("floors", "access_level", schema=schema)
    op.drop_column("floors", "capacity_type", schema=schema)
    op.drop_column("floors", "capacity", schema=schema)

    op.drop_constraint(
        "fk_branches_contact_person_user_id", "branches", type_="foreignkey", schema=schema
    )
    op.drop_column("branches", "notes", schema=schema)
    op.drop_column("branches", "operating_hours_to", schema=schema)
    op.drop_column("branches", "operating_hours_from", schema=schema)
    op.drop_column("branches", "contact_phone", schema=schema)
    op.drop_column("branches", "contact_email", schema=schema)
    op.drop_column("branches", "contact_person_user_id", schema=schema)
    op.drop_column("branches", "country", schema=schema)
    op.drop_column("branches", "city", schema=schema)

    op.drop_column("companies", "badge_expiry_duration_minutes", schema=schema)
    op.drop_column("companies", "auto_approve_pre_registered_visitors", schema=schema)
    op.drop_column("companies", "default_timezone", schema=schema)
