"""org structure: reception desk and security gate tri-state status

Revision ID: 524da546af26
Revises: c3e5aadc345f
Create Date: 2026-08-19 00:00:02.000000

The admin design shows a three-state status for both entities — Reception
Desk: Active/Maintenance/Inactive; Security Gate connectivity:
Online/Maintenance/Offline — which the existing boolean `is_active` cannot
represent. Adds `reception_desks.status` and
`security_gates.connectivity_status` as new string columns (new columns, not
a repurposed boolean, so the migration is a reviewable add-populate-drop
sequence per
openspec/changes/add-role-management-and-org-field-gaps/design.md
Decision 3), backfills each from the row's existing `is_active`
(`true` -> `active`/`online`, `false` -> `inactive`/`offline`), then drops
`is_active` from both tables. Also adds `SecurityGate.high_security` and
`SecurityGate.auth_method`, and `ReceptionDesk.assigned_receptionist_user_id`/
`operating_hours_from`/`operating_hours_to`.

Every `add_column`/`drop_column` below targets a table that already existed
before this migration, so each passes `schema=` explicitly (275bc2310f49's
landmine — `op.add_column`/`op.drop_column` do not honor
`schema_translate_map` the way `op.create_table` does). The backfill UPDATEs
are schema-qualified raw SQL for the same reason (`text()` never respects
`schema_translate_map`).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "524da546af26"
down_revision: str | None = "c3e5aadc345f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    bind = op.get_bind()

    op.add_column(
        "reception_desks", sa.Column("status", sa.String(length=20), nullable=True), schema=schema
    )
    op.add_column(
        "reception_desks",
        sa.Column("assigned_receptionist_user_id", sa.Uuid(), nullable=True),
        schema=schema,
    )
    op.add_column(
        "reception_desks",
        sa.Column("operating_hours_from", sa.String(length=10), nullable=True),
        schema=schema,
    )
    op.add_column(
        "reception_desks",
        sa.Column("operating_hours_to", sa.String(length=10), nullable=True),
        schema=schema,
    )
    bind.execute(
        sa.text(
            f'UPDATE "{schema}".reception_desks '
            f"SET status = CASE WHEN is_active THEN 'active' ELSE 'inactive' END"
        )
    )
    op.alter_column("reception_desks", "status", nullable=False, schema=schema)
    op.drop_column("reception_desks", "is_active", schema=schema)
    op.create_foreign_key(
        "fk_reception_desks_assigned_receptionist_user_id",
        "reception_desks",
        "users",
        ["assigned_receptionist_user_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )

    op.add_column(
        "security_gates",
        sa.Column("connectivity_status", sa.String(length=20), nullable=True),
        schema=schema,
    )
    op.add_column(
        "security_gates",
        sa.Column("high_security", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema=schema,
    )
    op.add_column(
        "security_gates", sa.Column("auth_method", sa.String(length=100), nullable=True), schema=schema
    )
    bind.execute(
        sa.text(
            f'UPDATE "{schema}".security_gates '
            f"SET connectivity_status = CASE WHEN is_active THEN 'online' ELSE 'offline' END"
        )
    )
    op.alter_column("security_gates", "connectivity_status", nullable=False, schema=schema)
    op.drop_column("security_gates", "is_active", schema=schema)


def downgrade() -> None:
    schema = _target_schema()
    bind = op.get_bind()

    op.drop_constraint(
        "fk_reception_desks_assigned_receptionist_user_id",
        "reception_desks",
        type_="foreignkey",
        schema=schema,
    )

    op.add_column(
        "security_gates",
        sa.Column("is_active", sa.Boolean(), nullable=True),
        schema=schema,
    )
    bind.execute(
        sa.text(
            f'UPDATE "{schema}".security_gates '
            f"SET is_active = (connectivity_status <> 'offline')"
        )
    )
    op.alter_column("security_gates", "is_active", nullable=False, schema=schema)
    op.drop_column("security_gates", "auth_method", schema=schema)
    op.drop_column("security_gates", "high_security", schema=schema)
    op.drop_column("security_gates", "connectivity_status", schema=schema)

    op.add_column(
        "reception_desks",
        sa.Column("is_active", sa.Boolean(), nullable=True),
        schema=schema,
    )
    bind.execute(
        sa.text(
            f'UPDATE "{schema}".reception_desks SET is_active = (status = \'active\')'
        )
    )
    op.alter_column("reception_desks", "is_active", nullable=False, schema=schema)
    op.drop_column("reception_desks", "operating_hours_to", schema=schema)
    op.drop_column("reception_desks", "operating_hours_from", schema=schema)
    op.drop_column("reception_desks", "assigned_receptionist_user_id", schema=schema)
    op.drop_column("reception_desks", "status", schema=schema)
