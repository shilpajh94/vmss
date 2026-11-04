"""zone_access_control: zones, gate links, allowed-zone mapping, access events

Revision ID: b9d4f1a6c3e8
Revises: f3b4c5d6e7a8
Create Date: 2026-11-04 00:00:00.000000

add-zone-access-control: five new tenant tables and four new permission codes
(`zones:manage`, `zones:view`, `access:scan`, `emergency:view`) granted to the
standard roles. `create_table` honours the connection's `schema_translate_map`,
so no explicit `schema=` there; the grant statements are schema-qualified by
hand like `a7c3e5f19b24`. Additive and idempotent. Downgrade drops the tables
and the grants and leaves the global catalog rows.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op
from vmss_api.core.config import settings

revision: str = "b9d4f1a6c3e8"
down_revision: str | Sequence[str] | None = "f3b4c5d6e7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GRANTS: dict[str, list[str]] = {
    "zones:manage": ["admin"],
    "zones:view": ["admin", "reception", "security"],
    "access:scan": ["admin", "security"],
    "emergency:view": ["admin", "reception", "security"],
}


def _now() -> sa.TextClause:
    return sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "zones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("building_id", sa.Uuid(), nullable=True),
        sa.Column("floor_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["building_id"], ["buildings.id"]),
        sa.ForeignKeyConstraint(["floor_id"], ["floors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_zones_branch_id", "zones", ["branch_id"])
    op.create_index(
        "uq_zone_branch_code",
        "zones",
        ["branch_id", "code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "zone_gates",
        sa.Column("zone_id", sa.Uuid(), nullable=False),
        sa.Column("gate_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gate_id"], ["security_gates.id"]),
        sa.PrimaryKeyConstraint("zone_id", "gate_id"),
    )
    op.create_index("ix_zone_gates_gate_id", "zone_gates", ["gate_id"])

    op.create_table(
        "visitor_category_zones",
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("zone_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["visitor_categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("category_id", "zone_id"),
    )
    op.create_index("ix_visitor_category_zones_zone_id", "visitor_category_zones", ["zone_id"])

    op.create_table(
        "invitation_zones",
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("zone_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.ForeignKeyConstraint(["invitation_id"], ["invitations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("invitation_id", "zone_id"),
    )
    op.create_index("ix_invitation_zones_zone_id", "invitation_zones", ["zone_id"])

    op.create_table(
        "zone_access_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("zone_id", sa.Uuid(), nullable=False),
        sa.Column("gate_id", sa.Uuid(), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("decision", sa.String(length=10), nullable=False),
        sa.Column("reason", sa.String(length=40), nullable=True),
        sa.Column("scanned_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.ForeignKeyConstraint(["invitation_id"], ["invitations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.id"]),
        sa.ForeignKeyConstraint(["gate_id"], ["security_gates.id"]),
        sa.ForeignKeyConstraint(["scanned_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_zone_access_events_invitation_occurred",
        "zone_access_events",
        ["invitation_id", "occurred_at"],
    )
    op.create_index(
        "ix_zone_access_events_zone_occurred", "zone_access_events", ["zone_id", "occurred_at"]
    )

    schema = op.get_context().version_table_schema
    global_schema = settings.global_schema_name
    conn = op.get_bind()
    for code, roles in _GRANTS.items():
        conn.execute(
            text(
                f'INSERT INTO "{global_schema}".permissions (id, code, description) '
                "VALUES (gen_random_uuid(), :code, :code) ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code},
        )
        for role in roles:
            conn.execute(
                text(
                    f'INSERT INTO "{schema}".role_permissions (role_id, permission_id) '
                    f'SELECT r.id, p.id FROM "{schema}".roles r '
                    f'CROSS JOIN "{global_schema}".permissions p '
                    "WHERE lower(r.name) = :role AND p.code = :code "
                    "ON CONFLICT DO NOTHING"
                ),
                {"code": code, "role": role},
            )


def downgrade() -> None:
    schema = op.get_context().version_table_schema
    global_schema = settings.global_schema_name
    conn = op.get_bind()
    for code in _GRANTS:
        conn.execute(
            text(
                f'DELETE FROM "{schema}".role_permissions WHERE permission_id IN '
                f'(SELECT id FROM "{global_schema}".permissions WHERE code = :code)'
            ),
            {"code": code},
        )
    op.drop_table("zone_access_events")
    op.drop_table("invitation_zones")
    op.drop_table("visitor_category_zones")
    op.drop_table("zone_gates")
    op.drop_table("zones")
