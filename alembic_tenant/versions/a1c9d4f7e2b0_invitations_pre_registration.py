"""invitations: pre-registration invites, visitors, and vehicles

Revision ID: a1c9d4f7e2b0
Revises: eb8de64c3468
Create Date: 2026-08-17 00:00:00.000000

Adds `invitations` (API-09's employee-created shell, completed by API-10's
self-registration submission), `invitation_visitors` (group co-visitors),
and `invitation_vehicles` — see
openspec/changes/add-pre-registration/design.md Decision 8. Purely additive.

No token/hash column on `invitations`: the registration-link/QR token is a
self-contained signed JWT (`core/security.py::create_invitation_token`),
verified without a database lookup — see `invitations/models.py`'s
`Invitation` docstring.

Hand-written, not `alembic revision --autogenerate` — same
`include_schemas=True` limitation as every migration in this tree
(see 275bc2310f49's docstring).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c9d4f7e2b0"
down_revision: str | None = "eb8de64c3468"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("registration_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("tracking_id", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("primary_contact_full_name", sa.String(length=255), nullable=False),
        sa.Column("primary_contact_email", sa.String(length=255), nullable=True),
        sa.Column("primary_contact_phone", sa.String(length=50), nullable=True),
        sa.Column(
            "primary_contact_preferred_contact_method", sa.String(length=10), nullable=False
        ),
        sa.Column("primary_contact_id_proof_type", sa.String(length=50), nullable=True),
        sa.Column("primary_contact_id_proof_storage_key", sa.String(length=500), nullable=True),
        sa.Column("purpose_of_visit", sa.String(length=255), nullable=True),
        sa.Column("host_name_or_email", sa.String(length=255), nullable=True),
        sa.Column("preferred_visit_date", sa.Date(), nullable=True),
        sa.Column("preferred_visit_time", sa.Time(), nullable=True),
        sa.Column("expected_duration", sa.String(length=50), nullable=True),
        sa.Column("department_to_visit", sa.String(length=255), nullable=True),
        sa.Column("additional_notes", sa.String(length=2000), nullable=True),
        sa.Column(
            "carried_items",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("carried_items_description", sa.String(length=2000), nullable=True),
        sa.Column("terms_accepted", sa.Boolean(), nullable=False),
        sa.Column("data_processing_accepted", sa.Boolean(), nullable=False),
        sa.Column("safety_guidelines_accepted", sa.Boolean(), nullable=False),
        sa.Column("consent_recorded_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tracking_id"),
    )
    op.create_index(op.f("ix_invitations_branch_id"), "invitations", ["branch_id"], unique=False)
    op.create_index(
        op.f("ix_invitations_created_by_user_id"), "invitations", ["created_by_user_id"],
        unique=False,
    )
    op.create_index(op.f("ix_invitations_status"), "invitations", ["status"], unique=False)
    op.create_index(
        op.f("ix_invitations_tracking_id"), "invitations", ["tracking_id"], unique=True
    )

    op.create_table(
        "invitation_visitors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("id_proof_type", sa.String(length=50), nullable=False),
        sa.Column("id_proof_storage_key", sa.String(length=500), nullable=False),
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
        sa.ForeignKeyConstraint(["invitation_id"], ["invitations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_invitation_visitors_invitation_id"),
        "invitation_visitors",
        ["invitation_id"],
        unique=False,
    )

    op.create_table(
        "invitation_vehicles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_type", sa.String(length=20), nullable=False),
        sa.Column("license_plate", sa.String(length=50), nullable=False),
        sa.Column("make_model", sa.String(length=255), nullable=True),
        sa.Column("color", sa.String(length=50), nullable=True),
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
        sa.ForeignKeyConstraint(["invitation_id"], ["invitations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_invitation_vehicles_invitation_id"),
        "invitation_vehicles",
        ["invitation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_invitation_vehicles_invitation_id"), table_name="invitation_vehicles"
    )
    op.drop_table("invitation_vehicles")

    op.drop_index(
        op.f("ix_invitation_visitors_invitation_id"), table_name="invitation_visitors"
    )
    op.drop_table("invitation_visitors")

    op.drop_index(op.f("ix_invitations_tracking_id"), table_name="invitations")
    op.drop_index(op.f("ix_invitations_status"), table_name="invitations")
    op.drop_index(op.f("ix_invitations_created_by_user_id"), table_name="invitations")
    op.drop_index(op.f("ix_invitations_branch_id"), table_name="invitations")
    op.drop_table("invitations")
