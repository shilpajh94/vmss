import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from vmss_api.core.database import Base, TimestampMixin

_NOT_DELETED = text("deleted_at IS NULL")


class FormStep(Base, TimestampMixin):
    """One draft registration step. `branch_id` is the scope this step
    belongs to: a specific branch, or `NULL` for the tenant-wide default —
    see `specs/form-builder/spec.md` "Configuration Is Branch-Scoped With a
    Tenant-Level Default". Mutating a step (create/update/delete/reorder)
    only ever touches this draft row; it has no effect on live invitation/
    registration submission until published into a `FormConfigVersion`
    snapshot for the same scope (design.md Decision 1).
    """

    __tablename__ = "form_steps"
    __table_args__ = (
        Index(
            "uq_form_step_branch_key",
            "branch_id",
            "key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND branch_id IS NOT NULL"),
        ),
        Index(
            "uq_form_step_default_key",
            "key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND branch_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("branches.id"), index=True)
    key: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(500))
    icon: Mapped[str | None] = mapped_column(String(50))
    # System steps are the six canonical ones seeded by `defaults.py`;
    # locked steps (Visitor Info, Visit Details, Review & Confirm) can never
    # be deactivated or deleted — see `specs/form-builder/spec.md` "Six
    # Canonical Steps Exist By Default".
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class FormFieldGroup(Base, TimestampMixin):
    """A named cluster of a `FormStep`'s fields (`specs/form-builder/spec.md`
    "A Step's Fields May Be Organized Into Named, Repeatable Field
    Groups"). When `is_repeatable` is set, the visitor-facing form lets the
    caller submit `min_instances`..`max_instances` (either bound `None` =
    unset) repetitions of the group's fields, each its own independent
    answer set — generalizing Vehicle Info's/Visitor Info's previously
    hard-coded "add another" behavior (design.md Decision 3/4 of
    `add-repeatable-field-groups`) to any step. A non-repeatable group is
    always exactly one instance.
    """

    __tablename__ = "form_field_groups"
    __table_args__ = (
        Index(
            "uq_form_field_group_branch_key",
            "branch_id",
            "key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND branch_id IS NOT NULL"),
        ),
        Index(
            "uq_form_field_group_default_key",
            "key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND branch_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    step_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("form_steps.id"), index=True)
    # Denormalized copy of the owning step's `branch_id`, needed only so the
    # two unique indexes above can enforce branch-wide (not just per-step)
    # group-key uniqueness the same way `uq_form_field_step_key`-style
    # indexes do for steps — kept in sync by `service.py` whenever a group
    # is created (a group is never moved to a different step/scope).
    branch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("branches.id"), index=True)
    key: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_repeatable: Mapped[bool] = mapped_column(Boolean, default=False)
    min_instances: Mapped[int | None] = mapped_column(Integer)
    max_instances: Mapped[int | None] = mapped_column(Integer)
    # `{"fieldKey": str, "operator": "equals" | "not_equals", "value": str}`
    # or `None` — same shape as `FormField.visibility_condition`, referencing
    # another field on the *same step* (specs/form-builder/spec.md "A Field
    # Group May Declare Conditional Visibility"). Independent of
    # `is_repeatable`: a group can be conditional only, repeatable only,
    # both, or neither.
    visibility_condition: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class FormField(Base, TimestampMixin):
    """One draft field within a `FormStep`. `is_locked` fields reject any
    attempt to change `is_active`/`is_required` via the API (a "system
    field" tier — see `specs/form-builder/spec.md` "System Fields Are
    Seeded With a Locked or Toggleable Tier"); non-locked fields (including
    every field of a fully-configurable step) may be freely edited/removed.
    """

    __tablename__ = "form_fields"
    __table_args__ = (
        Index(
            "uq_form_field_step_key",
            "step_id",
            "key",
            unique=True,
            postgresql_where=_NOT_DELETED,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    step_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("form_steps.id"), index=True)
    # Nullable: a field with no group assignment renders/submits as a flat
    # step-level field, unchanged from before field groups existed.
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("form_field_groups.id"), index=True
    )
    key: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(255))
    placeholder: Mapped[str | None] = mapped_column(String(255))
    help_text: Mapped[str | None] = mapped_column(String(500))
    field_type: Mapped[str] = mapped_column(String(30))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    # No backing column of its own for individual option strings — same
    # posture as `visitors.models.VisitorCategory.form_schema`'s `options`.
    options: Mapped[list[str] | None] = mapped_column(JSONB)
    validation_rules: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # `{"fieldKey": str, "operator": "equals" | "not_equals", "value": str}`
    # or `None` — see `specs/form-builder/spec.md` "A Field May Declare
    # Conditional Visibility".
    visibility_condition: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    width: Mapped[str] = mapped_column(String(10), default="full")
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class FormConfigVersion(Base, TimestampMixin):
    """The published, immutable-until-next-publish snapshot for one scope
    (a branch, or `NULL` for the tenant default) — what invitation/
    registration submission and the public/staff renderer actually read.
    Overwritten in place on every publish; no version history is kept
    (proposal's explicitly chosen scope for this iteration).
    """

    __tablename__ = "form_config_versions"
    __table_args__ = (
        Index(
            "uq_form_config_version_branch",
            "branch_id",
            unique=True,
            postgresql_where=text("branch_id IS NOT NULL"),
        ),
        # Postgres treats every NULL as distinct, so a plain unique index on
        # `branch_id` alone would never stop a second NULL-scope row from
        # being inserted. Indexing a constant expression, filtered to only
        # NULL-scope rows, is the standard way to cap that scope at exactly
        # one row.
        Index(
            "uq_form_config_version_default",
            text("(branch_id IS NULL)"),
            unique=True,
            postgresql_where=text("branch_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("branches.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
