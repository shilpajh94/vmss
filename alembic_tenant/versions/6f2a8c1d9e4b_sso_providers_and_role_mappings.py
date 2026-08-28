"""sso: providers and role mappings

Revision ID: 6f2a8c1d9e4b
Revises: 39c3f5112585
Create Date: 2026-08-24 00:00:00.000000

Adds `sso_providers` (a tenant's configured OIDC provider — API-19) and
`sso_role_mappings` (IdP-group-claim-value -> role, consulted by
just-in-time provisioning on first SSO login). Both tenant-scoped, plain
config tables — no branch scoping, same posture as `visitor_categories`.
See openspec/changes/add-sso-oidc-login/design.md.

Hand-written, not `alembic revision --autogenerate`, same as every other
migration in this tree (see 275bc2310f49's docstring).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6f2a8c1d9e4b"
down_revision: str | None = "39c3f5112585"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sso_providers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("discovery_url", sa.String(length=500), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret_encrypted", sa.String(length=1000), nullable=False),
        sa.Column("client_secret_masked", sa.String(length=20), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sso_role_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idp_group_claim_value", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idp_group_claim_value", name="uq_sso_role_mapping_group_claim"),
    )


def downgrade() -> None:
    op.drop_table("sso_role_mappings")
    op.drop_table("sso_providers")
