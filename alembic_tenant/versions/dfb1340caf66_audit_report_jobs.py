"""audit report jobs

Revision ID: dfb1340caf66
Revises: 15d7580a57ed
Create Date: 2026-09-01 00:00:00.000000

`add-audit-trail-history/design.md` Decision 2: adds `audit_report_jobs`,
one row per requested CSV/PDF audit-trail export. Purely additive — no
backfill needed, a tenant with no prior report requests simply has no rows.

`op.create_table` alone here (no `op.add_column`/`op.drop_column`), so it
already picks up the connection's `schema_translate_map` without an
explicit `schema=` kwarg — see `6f4e364ea9c8_device_tokens.py`'s docstring
for the same note.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dfb1340caf66"
down_revision: str | None = "15d7580a57ed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_report_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("formats", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("csv_storage_key", sa.String(length=500), nullable=True),
        sa.Column("pdf_storage_key", sa.String(length=500), nullable=True),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_report_jobs_requested_by_user_id"),
        "audit_report_jobs",
        ["requested_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_report_jobs_status"), "audit_report_jobs", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_report_jobs_status"), table_name="audit_report_jobs")
    op.drop_index(op.f("ix_audit_report_jobs_requested_by_user_id"), table_name="audit_report_jobs")
    op.drop_table("audit_report_jobs")
