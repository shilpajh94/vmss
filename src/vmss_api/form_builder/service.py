import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.form_builder.defaults import DEFAULT_EFFECTIVE_FORM, DEFAULT_STEP_SPECS
from vmss_api.form_builder.models import FormConfigVersion, FormField, FormFieldGroup, FormStep
from vmss_api.form_builder.repository import (
    FormConfigVersionRepository,
    FormFieldGroupRepository,
    FormFieldRepository,
    FormStepRepository,
)
from vmss_api.form_builder.schemas import (
    OPTION_REQUIRED_TYPES,
    FormFieldCreate,
    FormFieldGroupCreate,
    FormFieldGroupUpdate,
    FormFieldType,
    FormFieldUpdate,
    FormStepCreate,
    FormStepUpdate,
)

_CACHE_TTL_SECONDS = 300


def _cache_key(tenant_id: uuid.UUID, branch_id: uuid.UUID | None) -> str:
    return f"vmss:{tenant_id}:form-builder:effective:{branch_id or 'default'}"


# --- Seeding / clone-on-first-touch -----------------------------------------


async def seed_default_form_config(tenant_db: AsyncSession) -> None:
    """Idempotent: materializes the tenant-default draft (`branch_id=None`)
    from `DEFAULT_STEP_SPECS` if, and only if, it has no steps yet. Called
    at tenant provisioning (`platform/service.py::create_tenant`, mirroring
    `auth.rbac_catalog.seed_default_roles`) so a brand-new tenant's admin
    opens Form Builder to a pre-populated, editable starting point rather
    than a blank list — not a precondition for correct behavior, since
    `resolve_effective_form` below falls back to the same defaults in code
    even if this was never run.
    """
    await _materialize_defaults_if_empty(tenant_db, branch_id=None)
    await tenant_db.flush()


async def _materialize_defaults_if_empty(
    tenant_db: AsyncSession, branch_id: uuid.UUID | None
) -> None:
    step_repo = FormStepRepository(tenant_db)
    if await step_repo.count_for_scope(branch_id) > 0:
        return
    for step_order, step_spec in enumerate(DEFAULT_STEP_SPECS):
        step = FormStep(
            id=uuid.uuid4(),
            branch_id=branch_id,
            key=step_spec.key,
            name=step_spec.name,
            description=step_spec.description,
            icon=step_spec.icon,
            is_system=True,
            is_locked=step_spec.is_locked,
            is_active=True,
            order_index=step_order,
        )
        tenant_db.add(step)
        await tenant_db.flush()
        group_ids_by_key: dict[str, uuid.UUID] = {}
        for group_order, group_spec in enumerate(step_spec.groups):
            group = FormFieldGroup(
                id=uuid.uuid4(),
                step_id=step.id,
                branch_id=branch_id,
                key=group_spec.key,
                name=group_spec.name,
                is_system=True,
                is_locked=True,
                is_repeatable=group_spec.is_repeatable,
                min_instances=group_spec.min_instances,
                max_instances=group_spec.max_instances,
                visibility_condition=group_spec.visibility_condition,
                order_index=group_order,
            )
            tenant_db.add(group)
            await tenant_db.flush()
            group_ids_by_key[group_spec.key] = group.id
        for field_order, field_spec in enumerate(step_spec.fields):
            tenant_db.add(
                FormField(
                    id=uuid.uuid4(),
                    step_id=step.id,
                    group_id=group_ids_by_key.get(field_spec.group_key)
                    if field_spec.group_key
                    else None,
                    key=field_spec.key,
                    label=field_spec.label,
                    placeholder=field_spec.placeholder,
                    help_text=field_spec.help_text,
                    field_type=field_spec.field_type,
                    is_system=True,
                    is_locked=field_spec.is_locked,
                    is_active=field_spec.is_active,
                    is_required=field_spec.is_required,
                    options=field_spec.options,
                    validation_rules=None,
                    visibility_condition=None,
                    width="full",
                    hide_label=False,
                    order_index=field_order,
                )
            )


async def _ensure_scope_seeded(tenant_db: AsyncSession, branch_id: uuid.UUID | None) -> None:
    """Give a scope that has never been touched a real, editable starting
    point instead of an empty list — cloning the tenant-default's current
    draft when customizing a branch for the first time, or the built-in
    defaults for the tenant-default scope itself
    (specs/form-builder/spec.md "Configuration Is Branch-Scoped With a
    Tenant-Level Default").
    """
    step_repo = FormStepRepository(tenant_db)
    if await step_repo.count_for_scope(branch_id) > 0:
        return
    if branch_id is None:
        await _materialize_defaults_if_empty(tenant_db, branch_id=None)
        return
    source_steps = await step_repo.list_for_scope(None)
    if not source_steps:
        await _materialize_defaults_if_empty(tenant_db, branch_id=None)
        source_steps = await step_repo.list_for_scope(None)
    field_repo = FormFieldRepository(tenant_db)
    group_repo = FormFieldGroupRepository(tenant_db)
    for source_step in source_steps:
        new_step = FormStep(
            id=uuid.uuid4(),
            branch_id=branch_id,
            key=source_step.key,
            name=source_step.name,
            description=source_step.description,
            icon=source_step.icon,
            is_system=source_step.is_system,
            is_locked=source_step.is_locked,
            is_active=source_step.is_active,
            order_index=source_step.order_index,
        )
        tenant_db.add(new_step)
        await tenant_db.flush()
        new_group_ids_by_source_id: dict[uuid.UUID, uuid.UUID] = {}
        for source_group in await group_repo.list_for_step(source_step.id):
            new_group = FormFieldGroup(
                id=uuid.uuid4(),
                step_id=new_step.id,
                branch_id=branch_id,
                key=source_group.key,
                name=source_group.name,
                is_system=source_group.is_system,
                is_locked=source_group.is_locked,
                is_repeatable=source_group.is_repeatable,
                min_instances=source_group.min_instances,
                max_instances=source_group.max_instances,
                # Dropped, not copied — same posture as a field's own
                # `visibility_condition` a few lines below: the condition's
                # `fieldKey` is only meaningful once matched back to a real
                # field row on the *new* step, and cloning already forgoes
                # that reconciliation for fields, so groups stay consistent
                # with them rather than silently inserting an unvalidated
                # condition via direct row construction.
                visibility_condition=None,
                order_index=source_group.order_index,
            )
            tenant_db.add(new_group)
            await tenant_db.flush()
            new_group_ids_by_source_id[source_group.id] = new_group.id
        for source_field in await field_repo.list_for_step(source_step.id):
            tenant_db.add(
                FormField(
                    id=uuid.uuid4(),
                    step_id=new_step.id,
                    group_id=(
                        new_group_ids_by_source_id.get(source_field.group_id)
                        if source_field.group_id
                        else None
                    ),
                    key=source_field.key,
                    label=source_field.label,
                    placeholder=source_field.placeholder,
                    help_text=source_field.help_text,
                    field_type=source_field.field_type,
                    is_system=source_field.is_system,
                    is_locked=source_field.is_locked,
                    is_active=source_field.is_active,
                    is_required=source_field.is_required,
                    options=source_field.options,
                    validation_rules=source_field.validation_rules,
                    visibility_condition=None,  # re-validated per new step below if re-set later
                    width=source_field.width,
                    hide_label=source_field.hide_label,
                    order_index=source_field.order_index,
                )
            )


# --- Step CRUD ---------------------------------------------------------------


# A step's locked/non-locked tier is data (`is_locked`), but *which* locked
# key belongs at the front vs. the back is fixed identity — no endpoint lets
# an admin create a new locked step or flip `is_locked`, so these two tuples
# are the complete, permanent set (`defaults.py`).
_LEADING_LOCKED_KEYS: tuple[str, ...] = ("visitor_info", "visit_details")
_TRAILING_LOCKED_KEYS: tuple[str, ...] = ("review_confirm",)


def _rebuild_step_order(steps: list[FormStep], new_step: FormStep | None = None) -> list[FormStep]:
    """Leading locked steps (fixed key order), then every non-locked step in
    its current relative order to each other (a newly created step, if any,
    always lands last among these), then trailing locked steps (fixed key
    order) — the invariant `create_step`/`_ensure_step_order_valid` both
    uphold (design.md Decision 1/2 of `fix-form-builder-step-order-and-ui-gaps`).
    Returns the corrected list; the caller assigns `order_index` from its
    positions.
    """
    current_order = sorted(steps, key=lambda s: s.order_index)
    leading = [s for key in _LEADING_LOCKED_KEYS for s in current_order if s.key == key]
    trailing = [s for key in _TRAILING_LOCKED_KEYS for s in current_order if s.key == key]
    locked_ids = {s.id for s in leading} | {s.id for s in trailing}
    middle = [s for s in current_order if s.id not in locked_ids]
    if new_step is not None:
        middle = [*middle, new_step]
    return [*leading, *middle, *trailing]


async def _ensure_step_order_valid(tenant_db: AsyncSession, branch_id: uuid.UUID | None) -> None:
    """Idempotent, self-healing repair for the pre-existing bug where
    `create_step` could position a new custom step after the locked
    trailing run (e.g. after Review & Confirm) — a no-op once the order is
    already correct, so it's safe to call unconditionally on every scope
    access rather than requiring a separate migration/ops script.
    """
    repo = FormStepRepository(tenant_db)
    steps = await repo.list_for_scope(branch_id)
    if not steps:
        return
    current_order = sorted(steps, key=lambda s: s.order_index)
    corrected_order = _rebuild_step_order(steps)
    if [s.id for s in corrected_order] == [s.id for s in current_order]:
        return
    for index, step in enumerate(corrected_order):
        step.order_index = index
    await tenant_db.commit()


async def list_steps(tenant_db: AsyncSession, branch_id: uuid.UUID | None) -> list[FormStep]:
    await _ensure_scope_seeded(tenant_db, branch_id)
    await _ensure_step_order_valid(tenant_db, branch_id)
    return await FormStepRepository(tenant_db).list_for_scope(branch_id)


async def list_fields_for_steps(
    tenant_db: AsyncSession, steps: list[FormStep]
) -> dict[uuid.UUID, list[FormField]]:
    """One query for every step's fields (query-performance.md §2), grouped
    by `step_id` — not a per-step call in a loop.
    """
    fields_by_step: dict[uuid.UUID, list[FormField]] = {step.id: [] for step in steps}
    all_fields = await FormFieldRepository(tenant_db).list_for_steps([step.id for step in steps])
    for field in all_fields:
        fields_by_step[field.step_id].append(field)
    return fields_by_step


async def get_step(tenant_db: AsyncSession, step_id: uuid.UUID) -> FormStep:
    step = await FormStepRepository(tenant_db).get(step_id)
    if step is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Form step not found")
    return step


async def create_step(
    tenant_db: AsyncSession, branch_id: uuid.UUID | None, payload: FormStepCreate
) -> FormStep:
    await _ensure_scope_seeded(tenant_db, branch_id)
    await _ensure_step_order_valid(tenant_db, branch_id)
    repo = FormStepRepository(tenant_db)
    if await repo.get_by_key(branch_id, payload.key) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Step key already exists")
    existing_steps = await repo.list_for_scope(branch_id)
    step = FormStep(
        id=uuid.uuid4(),
        branch_id=branch_id,
        key=payload.key,
        name=payload.name,
        description=payload.description,
        icon=payload.icon,
        is_system=False,
        is_locked=False,
        is_active=True,
        order_index=0,
    )
    for index, ordered_step in enumerate(_rebuild_step_order(existing_steps, step)):
        ordered_step.order_index = index
    tenant_db.add(step)
    await tenant_db.commit()
    await tenant_db.refresh(step)
    return step


async def update_step(
    tenant_db: AsyncSession, step_id: uuid.UUID, payload: FormStepUpdate
) -> FormStep:
    step = await get_step(tenant_db, step_id)
    changes = payload.model_dump(exclude_unset=True)
    if step.is_locked and changes.get("is_active") is False:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A locked step cannot be deactivated"
        )
    for field_name, value in changes.items():
        setattr(step, field_name, value)
    await tenant_db.commit()
    await tenant_db.refresh(step)
    return step


async def delete_step(tenant_db: AsyncSession, step_id: uuid.UUID) -> None:
    step = await get_step(tenant_db, step_id)
    if step.is_locked:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A locked step cannot be removed"
        )
    await FormStepRepository(tenant_db).soft_delete(step)
    await tenant_db.commit()


def _assert_locked_positions_unchanged(
    current_order: list[uuid.UUID],
    ordered_ids: list[uuid.UUID],
    rows_by_id: dict[uuid.UUID, Any],
    *,
    detail: str,
) -> None:
    """specs/form-builder/spec.md "Fields and Steps Are Explicitly Ordered":
    a locked row must keep its position relative to every other locked
    sibling. Compared by position in the current order-sorted sequence, not
    by raw `order_index` value, so gaps left by a prior delete never affect
    the check (design.md Decision 1).
    """
    for position, current_id in enumerate(current_order):
        if rows_by_id[current_id].is_locked and ordered_ids[position] != current_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


async def reorder_steps(
    tenant_db: AsyncSession, branch_id: uuid.UUID | None, ordered_ids: list[uuid.UUID]
) -> list[FormStep]:
    await _ensure_step_order_valid(tenant_db, branch_id)
    repo = FormStepRepository(tenant_db)
    steps = await repo.list_for_scope(branch_id)
    steps_by_id = {s.id: s for s in steps}
    if set(ordered_ids) != set(steps_by_id):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="orderedIds must contain exactly this scope's current step ids",
        )
    current_order = [s.id for s in sorted(steps, key=lambda s: s.order_index)]
    _assert_locked_positions_unchanged(
        current_order,
        ordered_ids,
        steps_by_id,
        detail="A locked step's position cannot be changed by reordering",
    )
    for index, step_id in enumerate(ordered_ids):
        steps_by_id[step_id].order_index = index
    await tenant_db.commit()
    return await repo.list_for_scope(branch_id)


# --- Field CRUD ----------------------------------------------------------------


async def get_field(tenant_db: AsyncSession, field_id: uuid.UUID) -> FormField:
    field_row = await FormFieldRepository(tenant_db).get(field_id)
    if field_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Form field not found")
    return field_row


async def _fields_by_key_for_step(
    tenant_db: AsyncSession, step_id: uuid.UUID
) -> dict[str, FormField]:
    fields = await FormFieldRepository(tenant_db).list_for_step(step_id)
    return {f.key: f for f in fields}


def _check_visibility_condition(
    fields_by_key: dict[str, FormField], field_key: str, condition: dict[str, Any] | None
) -> None:
    """specs/form-builder/spec.md "A Field May Declare Conditional
    Visibility": the referenced field must exist in the same step, and no
    direct or transitive cycle may result.
    """
    if condition is None:
        return
    target_key = condition["fieldKey"]
    if target_key == field_key or target_key not in fields_by_key:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Conditional visibility must reference another field in the same step",
        )
    visited = {field_key}
    current: str | None = target_key
    while current is not None:
        if current in visited:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Conditional visibility must not form a cycle",
            )
        visited.add(current)
        current_field = fields_by_key.get(current)
        current_condition = current_field.visibility_condition if current_field else None
        current = current_condition["fieldKey"] if current_condition else None


def _check_group_visibility_condition(
    fields_by_key: dict[str, FormField],
    group_id: uuid.UUID | None,
    condition: dict[str, Any] | None,
) -> None:
    """specs/form-builder/spec.md "A Field Group May Declare Conditional
    Visibility": the referenced field must exist on the same step, and
    must not itself be a member of the group whose condition it's on (a
    group-level self-reference). No transitive-cycle walk is needed here
    — nothing can reference a group's own condition, so a group can never
    sit inside a cycle (design.md Decision 7 of
    `add-repeatable-field-groups`). `group_id` is `None` at group-creation
    time, when the group has no member fields yet and self-reference is
    therefore impossible.
    """
    if condition is None:
        return
    target_key = condition["fieldKey"]
    target_field = fields_by_key.get(target_key)
    if target_field is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Conditional visibility must reference another field in the same step",
        )
    if group_id is not None and target_field.group_id == group_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A group's conditional visibility cannot reference one of its own member fields",
        )


async def create_field(
    tenant_db: AsyncSession, step_id: uuid.UUID, payload: FormFieldCreate
) -> FormField:
    step = await get_step(tenant_db, step_id)
    repo = FormFieldRepository(tenant_db)
    if await repo.get_by_key(step_id, payload.key) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Field key already exists on this step"
        )
    if (
        await repo.get_by_key_in_branch(step.branch_id, payload.key, exclude_step_id=step_id)
        is not None
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Field key already exists on another step of this branch's form",
        )
    if payload.group_id is not None:
        group = await FormFieldGroupRepository(tenant_db).get(payload.group_id)
        if group is None or group.step_id != step_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="groupId must reference a group on this step",
            )
    fields_by_key = await _fields_by_key_for_step(tenant_db, step_id)
    condition = (
        payload.visibility_condition.model_dump(mode="json", by_alias=True)
        if (payload.visibility_condition)
        else None
    )
    _check_visibility_condition(fields_by_key, payload.key, condition)
    max_order = max((f.order_index for f in fields_by_key.values()), default=-1)
    field_row = FormField(
        id=uuid.uuid4(),
        step_id=step.id,
        group_id=payload.group_id,
        key=payload.key,
        label=payload.label,
        placeholder=payload.placeholder,
        help_text=payload.help_text,
        field_type=payload.field_type.value,
        is_system=False,
        is_locked=False,
        is_active=True,
        is_required=payload.is_required,
        options=payload.options,
        validation_rules=(
            payload.validation_rules.model_dump(mode="json", by_alias=True)
            if payload.validation_rules
            else None
        ),
        visibility_condition=condition,
        width=payload.width.value,
        hide_label=payload.hide_label,
        order_index=max_order + 1,
    )
    tenant_db.add(field_row)
    await tenant_db.commit()
    await tenant_db.refresh(field_row)
    return field_row


# System-seeded field keys whose value is consumed elsewhere as a specific
# structured type, not just rendered as form input, so their `field_type`
# stays fixed regardless of lock state: `email`/`phone`/
# `preferred_contact_method` back notification dispatch's deliverable
# address/channel (`invitations/schemas.py::_require_reachable_contact`/
# `_require_contact_for_method`); `registration_type` is a real enum and
# `list_invitations` filter column; `preferred_visit_date`/
# `preferred_visit_time` are real `Date`/`Time` DB columns consumed by
# overstay detection and the emergency report; `id_proof_upload`/
# `profile_photo` feed the file storage/PII pipeline;
# `visitor_category`'s real options come from the separate Visitor
# Category catalog (`_EXTERNALLY_CATALOGED_FIELD_KEYS`), not a `field_type`
# it makes sense to change. Every other system field is a plain string
# column with no such cross-cutting consumer, so its type is editable.
_TYPE_LOCKED_SYSTEM_FIELD_KEYS = frozenset(
    {
        "registration_type",
        "email",
        "phone",
        "preferred_contact_method",
        "visitor_category",
        "id_proof_upload",
        "profile_photo",
        "preferred_visit_date",
        "preferred_visit_time",
    }
)


async def update_field(
    tenant_db: AsyncSession, field_id: uuid.UUID, payload: FormFieldUpdate
) -> FormField:
    field_row = await get_field(tenant_db, field_id)
    changes = payload.model_dump(exclude_unset=True)

    if "group_id" in changes and changes["group_id"] is not None:
        group = await FormFieldGroupRepository(tenant_db).get(changes["group_id"])
        if group is None or group.step_id != field_row.step_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="groupId must reference a group on this field's step",
            )

    # Compares against an actual attempted transition, not merely whether
    # the key is present — the admin UI's save payload always resends every
    # property it manages (matching every other field's existing values
    # when untouched), so treating mere presence as "a change" would reject
    # an unrelated save (e.g. a label edit) on any already-`False`/already-
    # unchanged property purely because the frontend re-sent its current
    # value alongside it.
    if field_row.is_locked and (
        (changes.get("is_active") is False and field_row.is_active)
        or (changes.get("is_required") is False and field_row.is_required)
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A locked field's active/required state cannot be changed",
        )

    if (
        "field_type" in changes
        and field_row.key in _TYPE_LOCKED_SYSTEM_FIELD_KEYS
        and changes["field_type"] != field_row.field_type
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This field's type cannot be changed",
        )

    # Re-run field-creation's type-dependent checks against what this
    # field's type/required/help_text/options will be *after* this update
    # is applied — the payload's value where provided, the existing row's
    # value otherwise — not just the row's current, pre-update state.
    resulting_type = changes.get("field_type", field_row.field_type)
    resulting_is_required = changes.get("is_required", field_row.is_required)
    resulting_help_text = changes.get("help_text", field_row.help_text)
    resulting_options = changes.get("options", field_row.options)

    if resulting_type == FormFieldType.static_text:
        if resulting_is_required:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="A 'static_text' field cannot be required — it collects no value",
            )
        if not resulting_help_text or not resulting_help_text.strip():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="A 'static_text' field must declare non-empty 'helpText' content",
            )

    field_type_changing = "field_type" in changes and changes["field_type"] != field_row.field_type
    resulting_needs_options = (
        resulting_type in OPTION_REQUIRED_TYPES
        and field_row.key not in _EXTERNALLY_CATALOGED_FIELD_KEYS
    )
    if resulting_needs_options and not resulting_options:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"A '{resulting_type}' field must declare a non-empty 'options' list",
        )

    if (
        field_type_changing
        and resulting_type not in OPTION_REQUIRED_TYPES
        and "options" not in changes
    ):
        changes["options"] = None

    if field_type_changing:
        # `model_dump(exclude_unset=True)` keeps the Pydantic-typed enum
        # member (`FormFieldType`), not a plain string — normalize before
        # assigning to the column, matching `create_field`'s
        # `payload.field_type.value`.
        changes["field_type"] = changes["field_type"].value

    if "visibility_condition" in changes:
        fields_by_key = await _fields_by_key_for_step(tenant_db, field_row.step_id)
        fields_by_key[field_row.key] = field_row
        condition = (
            payload.visibility_condition.model_dump(mode="json", by_alias=True)
            if payload.visibility_condition
            else None
        )
        _check_visibility_condition(fields_by_key, field_row.key, condition)
        changes["visibility_condition"] = condition

    if "validation_rules" in changes:
        changes["validation_rules"] = (
            payload.validation_rules.model_dump(mode="json", by_alias=True)
            if payload.validation_rules
            else None
        )

    for attr, value in changes.items():
        setattr(field_row, attr, value)
    await tenant_db.commit()
    await tenant_db.refresh(field_row)
    return field_row


async def delete_field(tenant_db: AsyncSession, field_id: uuid.UUID) -> None:
    field_row = await get_field(tenant_db, field_id)
    if field_row.is_locked:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A locked field cannot be removed"
        )
    await FormFieldRepository(tenant_db).soft_delete(field_row)
    await tenant_db.commit()


async def reorder_fields(
    tenant_db: AsyncSession, step_id: uuid.UUID, ordered_ids: list[uuid.UUID]
) -> list[FormField]:
    repo = FormFieldRepository(tenant_db)
    fields = await repo.list_for_step(step_id)
    fields_by_id = {f.id: f for f in fields}
    if set(ordered_ids) != set(fields_by_id):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="orderedIds must contain exactly this step's current field ids",
        )
    current_order = [f.id for f in sorted(fields, key=lambda f: f.order_index)]
    _assert_locked_positions_unchanged(
        current_order,
        ordered_ids,
        fields_by_id,
        detail="A locked field's position cannot be changed by reordering",
    )
    for index, field_id in enumerate(ordered_ids):
        fields_by_id[field_id].order_index = index
    await tenant_db.commit()
    return await repo.list_for_step(step_id)


# --- Field Group CRUD -----------------------------------------------------------


async def list_groups_for_steps(
    tenant_db: AsyncSession, steps: list[FormStep]
) -> dict[uuid.UUID, list[FormFieldGroup]]:
    groups_by_step: dict[uuid.UUID, list[FormFieldGroup]] = {step.id: [] for step in steps}
    all_groups = await FormFieldGroupRepository(tenant_db).list_for_steps(
        [step.id for step in steps]
    )
    for group in all_groups:
        groups_by_step[group.step_id].append(group)
    return groups_by_step


async def get_group(tenant_db: AsyncSession, group_id: uuid.UUID) -> FormFieldGroup:
    group = await FormFieldGroupRepository(tenant_db).get(group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Field group not found")
    return group


# specs/form-builder/spec.md "Vehicle Info and Visitor Info Are Seeded as
# Locked, Repeatable Groups" — Visitor Info's co-visitor cardinality is
# governed exclusively by the registration-type rule, so its group exposes
# no admin-configurable minimum/maximum, unlike Vehicle Info's.
_NO_INSTANCE_RANGE_SYSTEM_GROUP_KEYS = frozenset({"visitors"})


async def create_group(
    tenant_db: AsyncSession, step_id: uuid.UUID, payload: FormFieldGroupCreate
) -> FormFieldGroup:
    step = await get_step(tenant_db, step_id)
    repo = FormFieldGroupRepository(tenant_db)
    if await repo.get_by_key(step_id, payload.key) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Group key already exists on this step"
        )
    if (
        await repo.get_by_key_in_branch(step.branch_id, payload.key, exclude_step_id=step_id)
        is not None
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Group key already exists on another step of this branch's form",
        )
    condition = (
        payload.visibility_condition.model_dump(mode="json", by_alias=True)
        if payload.visibility_condition
        else None
    )
    fields_by_key = await _fields_by_key_for_step(tenant_db, step_id)
    _check_group_visibility_condition(fields_by_key, None, condition)
    existing_groups = await repo.list_for_step(step_id)
    max_order = max((g.order_index for g in existing_groups), default=-1)
    group = FormFieldGroup(
        id=uuid.uuid4(),
        step_id=step.id,
        branch_id=step.branch_id,
        key=payload.key,
        name=payload.name,
        is_system=False,
        is_locked=False,
        is_repeatable=payload.is_repeatable,
        min_instances=payload.min_instances,
        max_instances=payload.max_instances,
        visibility_condition=condition,
        order_index=max_order + 1,
    )
    tenant_db.add(group)
    await tenant_db.commit()
    await tenant_db.refresh(group)
    return group


async def update_group(
    tenant_db: AsyncSession, group_id: uuid.UUID, payload: FormFieldGroupUpdate
) -> FormFieldGroup:
    group = await get_group(tenant_db, group_id)
    changes = payload.model_dump(exclude_unset=True)

    if (
        group.is_locked
        and group.key not in _NO_INSTANCE_RANGE_SYSTEM_GROUP_KEYS
        and changes.get("is_repeatable") is False
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A locked group cannot be made non-repeatable",
        )
    if group.key in _NO_INSTANCE_RANGE_SYSTEM_GROUP_KEYS and (
        "min_instances" in changes or "max_instances" in changes
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This group's instance count is governed by registration type, not a "
            "configurable range",
        )

    resulting_min = changes.get("min_instances", group.min_instances)
    resulting_max = changes.get("max_instances", group.max_instances)
    if resulting_min is not None and resulting_max is not None and resulting_min > resulting_max:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="minInstances must not be greater than maxInstances",
        )

    if "visibility_condition" in changes:
        fields_by_key = await _fields_by_key_for_step(tenant_db, group.step_id)
        condition = (
            payload.visibility_condition.model_dump(mode="json", by_alias=True)
            if payload.visibility_condition
            else None
        )
        _check_group_visibility_condition(fields_by_key, group.id, condition)
        changes["visibility_condition"] = condition

    for attr, value in changes.items():
        setattr(group, attr, value)
    await tenant_db.commit()
    await tenant_db.refresh(group)
    return group


async def delete_group(tenant_db: AsyncSession, group_id: uuid.UUID) -> None:
    group = await get_group(tenant_db, group_id)
    if group.is_locked:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A locked group cannot be removed"
        )
    field_repo = FormFieldRepository(tenant_db)
    for field_row in await field_repo.list_for_step(group.step_id):
        if field_row.group_id == group.id:
            field_row.group_id = None
    await FormFieldGroupRepository(tenant_db).soft_delete(group)
    await tenant_db.commit()


async def reorder_groups(
    tenant_db: AsyncSession, step_id: uuid.UUID, ordered_ids: list[uuid.UUID]
) -> list[FormFieldGroup]:
    repo = FormFieldGroupRepository(tenant_db)
    groups = await repo.list_for_step(step_id)
    groups_by_id = {g.id: g for g in groups}
    if set(ordered_ids) != set(groups_by_id):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="orderedIds must contain exactly this step's current group ids",
        )
    current_order = [g.id for g in sorted(groups, key=lambda g: g.order_index)]
    _assert_locked_positions_unchanged(
        current_order,
        ordered_ids,
        groups_by_id,
        detail="A locked group's position cannot be changed by reordering",
    )
    for index, group_id in enumerate(ordered_ids):
        groups_by_id[group_id].order_index = index
    await tenant_db.commit()
    return await repo.list_for_step(step_id)


# --- Publish / effective form --------------------------------------------------


# Exempt from `_requires_static_options` below — the only field whose real
# options come from somewhere other than its own `options` column: a live,
# separately admin-managed catalog (the `VisitorCategory` list), resolved
# at render time. Every other system-seeded dropdown/checkbox field (e.g.
# `id_proof_type`, `vehicle_type`) has no such external catalog — its
# `options` *is* the source of truth for what a submission may declare
# (make-id-proof-and-vehicle-type-configurable), so it needs the same
# non-empty-options guarantee any admin-authored field does.
_EXTERNALLY_CATALOGED_FIELD_KEYS = frozenset({"visitor_category"})


def _requires_static_options(field_row: FormField) -> bool:
    """See `_EXTERNALLY_CATALOGED_FIELD_KEYS` — every option-required field
    needs non-empty `options` except the one whose real options come from
    somewhere else entirely.
    """
    return field_row.key not in _EXTERNALLY_CATALOGED_FIELD_KEYS and field_row.field_type in {
        t.value for t in OPTION_REQUIRED_TYPES
    }


def _validate_draft_for_publish(
    steps: list[FormStep], fields_by_step: dict[uuid.UUID, list[FormField]]
) -> None:
    for step in steps:
        fields = fields_by_step.get(step.id, [])
        fields_by_key = {f.key: f for f in fields}
        for field_row in fields:
            if _requires_static_options(field_row) and not field_row.options:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Cannot publish: field '{field_row.key}' of type "
                        f"'{field_row.field_type}' has no options"
                    ),
                )
            _check_visibility_condition(
                fields_by_key, field_row.key, field_row.visibility_condition
            )


def _step_to_snapshot(
    step: FormStep, fields: list[FormField], groups: list[FormFieldGroup]
) -> dict[str, Any]:
    sorted_fields = sorted(fields, key=lambda x: x.order_index)
    field_keys_by_group_id: dict[uuid.UUID, list[str]] = {g.id: [] for g in groups}
    field_ids_by_group_id: dict[uuid.UUID, list[str]] = {g.id: [] for g in groups}
    for f in sorted_fields:
        if f.group_id in field_keys_by_group_id:
            field_keys_by_group_id[f.group_id].append(f.key)
            field_ids_by_group_id[f.group_id].append(str(f.id))
    return {
        "id": str(step.id),
        "branchId": str(step.branch_id) if step.branch_id else None,
        "key": step.key,
        "name": step.name,
        "description": step.description,
        "icon": step.icon,
        "isSystem": step.is_system,
        "isLocked": step.is_locked,
        "isActive": step.is_active,
        "orderIndex": step.order_index,
        "groups": [
            {
                "id": str(g.id),
                "stepId": str(g.step_id),
                "key": g.key,
                "name": g.name,
                "isSystem": g.is_system,
                "isLocked": g.is_locked,
                "isRepeatable": g.is_repeatable,
                "minInstances": g.min_instances,
                "maxInstances": g.max_instances,
                "visibilityCondition": g.visibility_condition,
                "orderIndex": g.order_index,
                # Kept for any lingering key-based reader; group membership
                # is resolved by `fieldIds` going forward
                # (restructure-walkin-payload-by-field-id).
                "fieldKeys": field_keys_by_group_id.get(g.id, []),
                "fieldIds": field_ids_by_group_id.get(g.id, []),
            }
            for g in sorted(groups, key=lambda x: x.order_index)
        ],
        "fields": [
            {
                "id": str(f.id),
                "stepId": str(f.step_id),
                "groupId": str(f.group_id) if f.group_id else None,
                "key": f.key,
                "label": f.label,
                "placeholder": f.placeholder,
                "helpText": f.help_text,
                "fieldType": f.field_type,
                "isSystem": f.is_system,
                "isLocked": f.is_locked,
                "isActive": f.is_active,
                "isRequired": f.is_required,
                "options": f.options,
                "validationRules": f.validation_rules,
                "visibilityCondition": f.visibility_condition,
                "width": f.width,
                "hideLabel": f.hide_label,
                "orderIndex": f.order_index,
            }
            for f in sorted_fields
        ],
    }


async def publish(
    tenant_db: AsyncSession,
    redis: Redis,
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
) -> FormConfigVersion:
    await _ensure_scope_seeded(tenant_db, branch_id)
    await _ensure_step_order_valid(tenant_db, branch_id)
    step_repo = FormStepRepository(tenant_db)
    steps = await step_repo.list_for_scope(branch_id)
    if not steps:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Nothing to publish for this scope"
        )
    fields_by_step = await list_fields_for_steps(tenant_db, steps)
    groups_by_step = await list_groups_for_steps(tenant_db, steps)
    _validate_draft_for_publish(steps, fields_by_step)

    snapshot = [
        _step_to_snapshot(step, fields_by_step.get(step.id, []), groups_by_step.get(step.id, []))
        for step in sorted(steps, key=lambda s: s.order_index)
        if step.is_active
    ]
    for step_snapshot in snapshot:
        step_snapshot["fields"] = [f for f in step_snapshot["fields"] if f["isActive"]]
        active_field_keys = {f["key"] for f in step_snapshot["fields"]}
        active_field_ids = {f["id"] for f in step_snapshot["fields"]}
        for group_snapshot in step_snapshot["groups"]:
            group_snapshot["fieldKeys"] = [
                k for k in group_snapshot["fieldKeys"] if k in active_field_keys
            ]
            group_snapshot["fieldIds"] = [
                i for i in group_snapshot["fieldIds"] if i in active_field_ids
            ]

    version_repo = FormConfigVersionRepository(tenant_db)
    existing = await version_repo.get_for_scope(branch_id)
    if existing is None:
        existing = FormConfigVersion(
            id=uuid.uuid4(), branch_id=branch_id, version=1, snapshot=snapshot
        )
        tenant_db.add(existing)
    else:
        existing.version += 1
        existing.snapshot = snapshot
        existing.published_at = datetime.now(UTC)
    existing.published_by_user_id = actor_user_id
    await tenant_db.commit()
    await tenant_db.refresh(existing)

    await redis.delete(_cache_key(tenant_id, branch_id))
    return existing


async def resolve_effective_form(
    tenant_db: AsyncSession, redis: Redis, *, tenant_id: uuid.UUID, branch_id: uuid.UUID | None
) -> list[dict[str, Any]]:
    """Branch -> tenant-default -> in-code fallback, per
    specs/form-builder/spec.md "Configuration Is Branch-Scoped With a
    Tenant-Level Default". Cached in Redis (design.md Decision 6) since this
    sits on the invitation/registration-submission hot path.
    """
    branch_cache_key = _cache_key(tenant_id, branch_id)
    default_cache_key = _cache_key(tenant_id, None)

    cached = await redis.get(branch_cache_key)
    if cached is not None:
        result: list[dict[str, Any]] = json.loads(cached)
        return result
    if branch_id is not None:
        # A prior request for this branch may have fallen back to the
        # tenant-default snapshot and cached it under `default_cache_key`
        # (see below) rather than `branch_cache_key` - check there before
        # hitting the DB so the fallback path stays cache-hot too.
        cached_default = await redis.get(default_cache_key)
        if cached_default is not None:
            result = json.loads(cached_default)
            return result

    version_repo = FormConfigVersionRepository(tenant_db)
    version = await version_repo.get_for_scope(branch_id)
    if version is not None:
        snapshot = version.snapshot
        await redis.set(branch_cache_key, json.dumps(snapshot), ex=_CACHE_TTL_SECONDS)
        return snapshot

    if branch_id is not None:
        version = await version_repo.get_for_scope(None)
    snapshot = version.snapshot if version is not None else DEFAULT_EFFECTIVE_FORM
    # Cache the tenant-default fallback under the default's own cache key
    # (not the requesting branch's) so that publish(branch_id=None)'s single
    # `redis.delete(_cache_key(tenant_id, None))` invalidates it for every
    # branch currently riding the default, instead of leaving stale
    # per-branch copies to expire on their own TTL.
    await redis.set(default_cache_key, json.dumps(snapshot), ex=_CACHE_TTL_SECONDS)
    return snapshot
