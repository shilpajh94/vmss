"""devices, tenant_settings, and invitation check-in/out device columns

Revision ID: f2a4c6e8b0d1
Revises: e5f7a9b1c3d4
Create Date: 2026-10-14 00:00:00.000000

Additive only. Also grants the new `devices:*` / `settings:*` permissions to
every role named `admin` in this tenant (the standard Admin role holds the
whole catalog; `seed_default_roles` only covers newly provisioned tenants).
Idempotent: catalog insert and grants skip existing rows.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op
from vmss_api.core.config import settings

# revision identifiers, used by Alembic.
revision: str = "f2a4c6e8b0d1"
down_revision: str | Sequence[str] | None = "e5f7a9b1c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_PERMISSIONS = (
    "devices:view",
    "devices:manage",
    "devices:approve",
    "settings:view",
    "settings:manage",
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("building_id", sa.Uuid(), nullable=True),
        sa.Column("operating_mode", sa.String(length=20), nullable=False),
        sa.Column("approval_status", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["building_id"], ["buildings.id"]),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"], ["users.id"], name="fk_devices_approved_by_user_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_devices_branch_id"), "devices", ["branch_id"])
    op.create_index(op.f("ix_devices_building_id"), "devices", ["building_id"])
    op.create_index(op.f("ix_devices_operating_mode"), "devices", ["operating_mode"])
    op.create_index(op.f("ix_devices_approval_status"), "devices", ["approval_status"])
    op.create_index(
        "uq_devices_device_id",
        "devices",
        ["device_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "tenant_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "enforce_kiosk_location_validation",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    # ALTERs on an existing table don't honor the connection's
    # `schema_translate_map` (unlike `create_table` above), so the target
    # schema is passed explicitly — same as d4e9a2b7c1f6.
    schema = op.get_context().version_table_schema
    for column in ("check_in_device_id", "check_out_device_id"):
        op.add_column("invitations", sa.Column(column, sa.Uuid(), nullable=True), schema=schema)
        op.create_foreign_key(
            f"fk_invitations_{column}",
            "invitations",
            "devices",
            [column],
            ["id"],
            source_schema=schema,
            referent_schema=schema,
        )
        op.create_index(op.f(f"ix_invitations_{column}"), "invitations", [column], schema=schema)

    _grant_permissions()


def _grant_permissions() -> None:
    schema = op.get_context().version_table_schema
    global_schema = settings.global_schema_name
    conn = op.get_bind()
    for code in _NEW_PERMISSIONS:
        conn.execute(
            text(
                f'INSERT INTO "{global_schema}".permissions (id, code, description) '
                "VALUES (gen_random_uuid(), :code, :code) ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code},
        )
        conn.execute(
            text(
                f'INSERT INTO "{schema}".role_permissions (role_id, permission_id) '
                f'SELECT r.id, p.id FROM "{schema}".roles r '
                f'CROSS JOIN "{global_schema}".permissions p '
                "WHERE lower(r.name) = 'admin' AND p.code = :code ON CONFLICT DO NOTHING"
            ),
            {"code": code},
        )


def downgrade() -> None:
    schema = op.get_context().version_table_schema
    global_schema = settings.global_schema_name
    op.get_bind().execute(
        text(
            f'DELETE FROM "{schema}".role_permissions WHERE permission_id IN '
            f'(SELECT id FROM "{global_schema}".permissions WHERE code = ANY(:codes))'
        ),
        {"codes": list(_NEW_PERMISSIONS)},
    )
    for column in ("check_out_device_id", "check_in_device_id"):
        op.drop_index(op.f(f"ix_invitations_{column}"), table_name="invitations", schema=schema)
        op.drop_constraint(
            f"fk_invitations_{column}", "invitations", schema=schema, type_="foreignkey"
        )
        op.drop_column("invitations", column, schema=schema)
    op.drop_table("tenant_settings")
    op.drop_index("uq_devices_device_id", table_name="devices")
    op.drop_index(op.f("ix_devices_approval_status"), table_name="devices")
    op.drop_index(op.f("ix_devices_operating_mode"), table_name="devices")
    op.drop_index(op.f("ix_devices_building_id"), table_name="devices")
    op.drop_index(op.f("ix_devices_branch_id"), table_name="devices")
    op.drop_table("devices")
