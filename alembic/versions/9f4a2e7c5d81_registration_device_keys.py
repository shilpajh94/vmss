"""registration_device_keys: walk-in kiosk/app device credentials

Revision ID: 9f4a2e7c5d81
Revises: 02dfcb7b1ddc
Create Date: 2026-08-19 00:00:00.000000

API-13 (`add-walkin-visitor-registration`): resolves `POST
/registrations/walk-in`'s caller (a provisioned kiosk/app instance, not a
JWT-bearing user) to a fixed tenant + branch — see
add-walkin-visitor-registration/design.md Decision 3. Lives in the global
schema, same as `tenant_user_index`, since the request must resolve which
tenant schema to open before anything tenant-scoped can be checked.

No `ForeignKeyConstraint` on `branch_id`: `branches` lives inside each
tenant's own physical schema, not a single global one, so there is no
cross-schema-safe FK target — same reasoning as `tenant_user_index.user_id`
having none either.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9f4a2e7c5d81"
down_revision: str | None = "02dfcb7b1ddc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "global"


def upgrade() -> None:
    op.create_table(
        "registration_device_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["global.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_global_registration_device_keys_tenant_id"),
        "registration_device_keys",
        ["tenant_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_global_registration_device_keys_branch_id"),
        "registration_device_keys",
        ["branch_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_global_registration_device_keys_branch_id"),
        table_name="registration_device_keys",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f("ix_global_registration_device_keys_tenant_id"),
        table_name="registration_device_keys",
        schema=SCHEMA,
    )
    op.drop_table("registration_device_keys", schema=SCHEMA)
