import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from vmss_api.core.database import Base, TimestampMixin

# Scopes each partial unique index below to non-deleted rows, so a
# soft-deleted row's name/code/step is freed for reuse — same fix and
# rationale as org_structure/models.py's `_NOT_DELETED`. See
# openspec/changes/harden-visitor-types-crud/design.md Decision 1.
_NOT_DELETED = text("deleted_at IS NULL")


class VisitorCategory(Base, TimestampMixin):
    """A configurable visitor type (e.g. "Vendor", "Interview Candidate",
    "Contractor", "Guest"). `form_schema` is a JSON list of field
    definitions (`schemas.py::FormFieldDefinition`) describing what a
    pre-registration/check-in form for this category collects beyond the
    fixed visitor fields — validated at the API boundary
    (security-architecture.md §4) before it's ever stored here.

    Whether/how a visit of this category needs approval is deliberately not
    a column on this table — it's zero-or-more `ApprovalWorkflowRule` rows;
    no rows means walk-in/pre-approved.
    """

    __tablename__ = "visitor_categories"
    __table_args__ = (
        Index("visitor_categories_name_key", "name", unique=True, postgresql_where=_NOT_DELETED),
        Index("ix_visitor_categories_code", "code", unique=True, postgresql_where=_NOT_DELETED),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(String(500))
    form_schema: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ApprovalWorkflowRule(Base, TimestampMixin):
    """One ordered step in a `VisitorCategory`'s approval chain: the
    approver at `step_order` is whoever holds `approver_role_id`.

    Configuration only — evaluating these rules against an actual visit
    request is the (not-yet-built) `approvals` feature's job
    (`project-rules.md`'s directory-structure note), the same way
    `org_structure`'s tables describe the org chart without owning check-in
    behavior themselves.

    No ORM `relationship` to `auth.models.Role`: same posture as
    `auth.models.User.department_id` referencing `org_structure` by column
    only — avoids a cross-feature import cycle for a link only ever resolved
    through `auth.repository.RoleRepository`, never traversed as an
    attribute.
    """

    __tablename__ = "approval_workflow_rules"
    __table_args__ = (
        Index(
            "uq_workflow_rule_category_step",
            "visitor_category_id",
            "step_order",
            unique=True,
            postgresql_where=_NOT_DELETED,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    visitor_category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("visitor_categories.id"), index=True
    )
    step_order: Mapped[int] = mapped_column(Integer)
    approver_role_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("roles.id"), index=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    escalation_minutes: Mapped[int | None] = mapped_column(Integer)
    auto_approve_minutes: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
