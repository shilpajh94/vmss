"""invitation approval steps and invitation visitor category

Revision ID: a3f7c92e1d44
Revises: 787f2f641092
Create Date: 2026-08-31 00:00:00.000000

`invitation-multi-step-approval/design.md` Migration Plan step 1: tags
`invitations` with the `VisitorCategory` it was submitted under (nullable —
existing rows have none; `InvitationCreate` requires it going forward, at
the request-validation layer only), and adds `invitation_approval_steps`, the
per-invitation snapshot of a category's active `ApprovalWorkflowRule`s at
submission time.

`op.add_column` for `invitations.visitor_category_id` passes `schema=` explicitly
— it does not pick up the connection's `schema_translate_map` the way
`op.create_table` does (same verified gotcha `787f2f641092`'s docstring
documents).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f7c92e1d44"
down_revision: str | None = "787f2f641092"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Scopes the `(invitation_id, step_order)` uniqueness to non-deleted rows —
# a *partial* unique index via `op.create_index`, not `sa.UniqueConstraint`,
# so a soft-deleted step's slot is reusable. Getting this right from table
# creation, unlike `eb8de64c3468`'s `approval_workflow_rules`, which shipped
# as a full constraint and needed `2b57bd4b7d9d` to fix it after the fact.
_NOT_DELETED = sa.text("deleted_at IS NULL")


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()

    op.add_column(
        "invitations",
        sa.Column("visitor_category_id", sa.Uuid(), nullable=True),
        schema=schema,
    )
    op.create_index(
        "ix_invitations_visitor_category_id",
        "invitations",
        ["visitor_category_id"],
        schema=schema,
    )
    op.create_foreign_key(
        "fk_invitations_visitor_category_id_visitor_categories",
        "invitations",
        "visitor_categories",
        ["visitor_category_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )

    op.create_table(
        "invitation_approval_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("approver_role_id", sa.Uuid(), nullable=False),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("acted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalation_minutes", sa.Integer(), nullable=True),
        sa.Column("auto_approve_minutes", sa.Integer(), nullable=True),
        sa.Column("escalates_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_approves_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["approver_role_id"], ["roles.id"]),
        sa.ForeignKeyConstraint(["acted_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_approval_step_invitation_step",
        "invitation_approval_steps",
        ["invitation_id", "step_order"],
        unique=True,
        postgresql_where=_NOT_DELETED,
    )
    op.create_index(
        op.f("ix_invitation_approval_steps_invitation_id"),
        "invitation_approval_steps",
        ["invitation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_invitation_approval_steps_approver_role_id"),
        "invitation_approval_steps",
        ["approver_role_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_invitation_approval_steps_status"),
        "invitation_approval_steps",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    schema = _target_schema()

    op.drop_index(
        op.f("ix_invitation_approval_steps_status"), table_name="invitation_approval_steps"
    )
    op.drop_index(
        op.f("ix_invitation_approval_steps_approver_role_id"),
        table_name="invitation_approval_steps",
    )
    op.drop_index(
        op.f("ix_invitation_approval_steps_invitation_id"),
        table_name="invitation_approval_steps",
    )
    op.drop_index("uq_approval_step_invitation_step", table_name="invitation_approval_steps")
    op.drop_table("invitation_approval_steps")

    op.drop_constraint(
        "fk_invitations_visitor_category_id_visitor_categories",
        "invitations",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_index("ix_invitations_visitor_category_id", table_name="invitations", schema=schema)
    op.drop_column("invitations", "visitor_category_id", schema=schema)
