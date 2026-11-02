import uuid
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.audit import record_audit_log
from vmss_api.auth.models import User
from vmss_api.core.deps import get_current_user, get_tenant, get_tenant_db
from vmss_api.core.rate_limit import limiter
from vmss_api.core.redis import get_redis
from vmss_api.core.responses import success_response
from vmss_api.core.schemas import Envelope
from vmss_api.form_builder import service
from vmss_api.form_builder.deps import (
    public_optional_branch_id,
    public_tenant,
    public_tenant_db,
    require_form_scope,
)
from vmss_api.form_builder.models import FormField, FormFieldGroup, FormStep
from vmss_api.form_builder.schemas import (
    FormFieldCreate,
    FormFieldGroupCreate,
    FormFieldGroupOut,
    FormFieldGroupUpdate,
    FormFieldOut,
    FormFieldUpdate,
    FormStepCreate,
    FormStepOut,
    FormStepUpdate,
    PublishOut,
    ReorderRequest,
    VisibilityCondition,
)
from vmss_api.form_builder.snapshot import is_supported_field_type, supported_field_rows
from vmss_api.form_builder.step_icons import resolve_step_icon
from vmss_api.tenant.models import Tenant

router = APIRouter(prefix="/form-builder", tags=["form-builder"])


def _fields_out(fields: list[FormField], *, source: str) -> list[FormFieldOut]:
    """Serializes a step's fields in order, skipping any stored row whose
    type has since left the catalog (heal-stale-form-config-data): one such
    row would otherwise fail `FormFieldOut`'s enum and 500 the whole read.
    """
    return [
        FormFieldOut.model_validate(f)
        for f in sorted(supported_field_rows(fields, source=source), key=lambda x: x.order_index)
    ]


def _group_out(group: FormFieldGroup, fields: list[FormField]) -> FormFieldGroupOut:
    return FormFieldGroupOut(
        id=group.id,
        step_id=group.step_id,
        key=group.key,
        name=group.name,
        is_system=group.is_system,
        is_locked=group.is_locked,
        is_repeatable=group.is_repeatable,
        min_instances=group.min_instances,
        max_instances=group.max_instances,
        visibility_condition=(
            VisibilityCondition.model_validate(group.visibility_condition)
            if group.visibility_condition is not None
            else None
        ),
        order_index=group.order_index,
        field_ids=[
            f.id for f in fields if f.group_id == group.id and is_supported_field_type(f.field_type)
        ],
    )


def _step_out(
    step: FormStep, fields: list[FormField], groups: list[FormFieldGroup] | None = None
) -> FormStepOut:
    return FormStepOut(
        id=step.id,
        branch_id=step.branch_id,
        key=step.key,
        name=step.name,
        description=step.description,
        icon=resolve_step_icon(step.icon, step.name),
        is_system=step.is_system,
        is_locked=step.is_locked,
        is_active=step.is_active,
        order_index=step.order_index,
        fields=_fields_out(fields, source="admin_steps"),
        groups=[_group_out(g, fields) for g in sorted(groups or [], key=lambda x: x.order_index)],
    )


def _ensure_in_scope(
    owner_branch_id: uuid.UUID | None, resolved_branch_id: uuid.UUID | None
) -> None:
    """Defense in depth: a step/field id path param must belong to the
    scope the caller's `X-Branch-ID` (or its absence) resolved to — not
    merely to *some* scope the caller happens to hold the permission at.
    """
    if owner_branch_id != resolved_branch_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found in this scope")


# --- Steps --------------------------------------------------------------------


@router.get("/steps", response_model=Envelope[list[FormStepOut]])
async def list_steps(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_id: Annotated[uuid.UUID | None, Depends(require_form_scope("form-builder:view"))],
) -> JSONResponse:
    steps = await service.list_steps(tenant_db, branch_id)
    fields_by_step = await service.list_fields_for_steps(tenant_db, steps)
    groups_by_step = await service.list_groups_for_steps(tenant_db, steps)
    return success_response(
        data=[
            _step_out(s, fields_by_step.get(s.id, []), groups_by_step.get(s.id, [])) for s in steps
        ]
    )


class _FormAudit:
    """Queues one audit-log entry per form-builder mutation, off the request
    path (audit-trail delta "Form-Builder, Profile, and Platform Mutations
    Are Audited"; security-architecture.md §5)."""

    def __init__(self, background_tasks: BackgroundTasks, tenant: Tenant, user: User) -> None:
        self._background_tasks = background_tasks
        self._tenant = tenant
        self._user = user

    def record(
        self,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
        diff: dict[str, Any] | None = None,
    ) -> None:
        self._background_tasks.add_task(
            record_audit_log,
            self._tenant.schema_name,
            actor_user_id=self._user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            diff=diff,
        )


def _form_audit(
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    user: Annotated[User, Depends(get_current_user)],
) -> _FormAudit:
    return _FormAudit(background_tasks, tenant, user)


@router.post("/steps", response_model=Envelope[FormStepOut], status_code=status.HTTP_201_CREATED)
async def create_step(
    payload: FormStepCreate,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_id: Annotated[uuid.UUID | None, Depends(require_form_scope("form-builder:manage"))],
    audit: Annotated[_FormAudit, Depends(_form_audit)],
) -> JSONResponse:
    step = await service.create_step(tenant_db, branch_id, payload)
    audit.record("form_step_created", "FormStep", step.id, {"key": step.key})
    return success_response(data=_step_out(step, [], []), status_code=status.HTTP_201_CREATED)


@router.patch("/steps/{step_id}", response_model=Envelope[FormStepOut])
async def update_step(
    step_id: uuid.UUID,
    payload: FormStepUpdate,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_id: Annotated[uuid.UUID | None, Depends(require_form_scope("form-builder:manage"))],
    audit: Annotated[_FormAudit, Depends(_form_audit)],
) -> JSONResponse:
    step = await service.get_step(tenant_db, step_id)
    _ensure_in_scope(step.branch_id, branch_id)
    step = await service.update_step(tenant_db, step_id, payload)
    audit.record(
        "form_step_updated",
        "FormStep",
        step.id,
        payload.model_dump(exclude_unset=True, mode="json"),
    )
    fields = await service.list_fields_for_steps(tenant_db, [step])
    groups = await service.list_groups_for_steps(tenant_db, [step])
    return success_response(data=_step_out(step, fields.get(step.id, []), groups.get(step.id, [])))


@router.delete("/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_step(
    step_id: uuid.UUID,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_id: Annotated[uuid.UUID | None, Depends(require_form_scope("form-builder:manage"))],
    audit: Annotated[_FormAudit, Depends(_form_audit)],
) -> None:
    step = await service.get_step(tenant_db, step_id)
    _ensure_in_scope(step.branch_id, branch_id)
    await service.delete_step(tenant_db, step_id)
    audit.record("form_step_deleted", "FormStep", step_id)


@router.post("/steps/reorder", response_model=Envelope[list[FormStepOut]])
async def reorder_steps(
    payload: ReorderRequest,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_id: Annotated[uuid.UUID | None, Depends(require_form_scope("form-builder:manage"))],
    audit: Annotated[_FormAudit, Depends(_form_audit)],
) -> JSONResponse:
    steps = await service.reorder_steps(tenant_db, branch_id, payload.ordered_ids)
    audit.record(
        "form_steps_reordered",
        "FormStep",
        None,
        {"orderedIds": [str(i) for i in payload.ordered_ids]},
    )
    fields_by_step = await service.list_fields_for_steps(tenant_db, steps)
    groups_by_step = await service.list_groups_for_steps(tenant_db, steps)
    return success_response(
        data=[
            _step_out(s, fields_by_step.get(s.id, []), groups_by_step.get(s.id, [])) for s in steps
        ]
    )


# --- Fields ---------------------------------------------------------------------


@router.get("/steps/{step_id}/fields", response_model=Envelope[list[FormFieldOut]])
async def list_fields(
    step_id: uuid.UUID,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_id: Annotated[uuid.UUID | None, Depends(require_form_scope("form-builder:view"))],
) -> JSONResponse:
    step = await service.get_step(tenant_db, step_id)
    _ensure_in_scope(step.branch_id, branch_id)
    fields = await service.list_fields_for_steps(tenant_db, [step])
    return success_response(data=_fields_out(fields.get(step.id, []), source="admin_fields"))


@router.post(
    "/steps/{step_id}/fields",
    response_model=Envelope[FormFieldOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_field(
    step_id: uuid.UUID,
    payload: FormFieldCreate,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_id: Annotated[uuid.UUID | None, Depends(require_form_scope("form-builder:manage"))],
    audit: Annotated[_FormAudit, Depends(_form_audit)],
) -> JSONResponse:
    step = await service.get_step(tenant_db, step_id)
    _ensure_in_scope(step.branch_id, branch_id)
    field_row = await service.create_field(tenant_db, step_id, payload)
    audit.record("form_field_created", "FormField", field_row.id, {"key": field_row.key})
    return success_response(
        data=FormFieldOut.model_validate(field_row), status_code=status.HTTP_201_CREATED
    )


@router.patch("/fields/{field_id}", response_model=Envelope[FormFieldOut])
async def update_field(
    field_id: uuid.UUID,
    payload: FormFieldUpdate,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_id: Annotated[uuid.UUID | None, Depends(require_form_scope("form-builder:manage"))],
    audit: Annotated[_FormAudit, Depends(_form_audit)],
) -> JSONResponse:
    field_row = await service.get_field(tenant_db, field_id)
    step = await service.get_step(tenant_db, field_row.step_id)
    _ensure_in_scope(step.branch_id, branch_id)
    if not is_supported_field_type(field_row.field_type) and payload.field_type is None:
        # Retyping is how an admin repairs a field of a removed type; any
        # other edit would have to serialize the unsupported type back out.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Field type '{field_row.field_type}' is no longer supported; "
                "set a supported fieldType to edit this field"
            ),
        )
    field_row = await service.update_field(tenant_db, field_id, payload)
    audit.record(
        "form_field_updated",
        "FormField",
        field_id,
        payload.model_dump(exclude_unset=True, mode="json"),
    )
    return success_response(data=FormFieldOut.model_validate(field_row))


@router.delete("/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_field(
    field_id: uuid.UUID,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_id: Annotated[uuid.UUID | None, Depends(require_form_scope("form-builder:manage"))],
    audit: Annotated[_FormAudit, Depends(_form_audit)],
) -> None:
    field_row = await service.get_field(tenant_db, field_id)
    step = await service.get_step(tenant_db, field_row.step_id)
    _ensure_in_scope(step.branch_id, branch_id)
    await service.delete_field(tenant_db, field_id)
    audit.record("form_field_deleted", "FormField", field_id)


@router.post("/steps/{step_id}/fields/reorder", response_model=Envelope[list[FormFieldOut]])
async def reorder_fields(
    step_id: uuid.UUID,
    payload: ReorderRequest,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_id: Annotated[uuid.UUID | None, Depends(require_form_scope("form-builder:manage"))],
    audit: Annotated[_FormAudit, Depends(_form_audit)],
) -> JSONResponse:
    step = await service.get_step(tenant_db, step_id)
    _ensure_in_scope(step.branch_id, branch_id)
    fields = await service.reorder_fields(tenant_db, step_id, payload.ordered_ids)
    audit.record(
        "form_fields_reordered",
        "FormStep",
        step_id,
        {"orderedIds": [str(i) for i in payload.ordered_ids]},
    )
    return success_response(data=_fields_out(fields, source="admin_reorder"))


# --- Field Groups --------------------------------------------------------------


@router.get("/steps/{step_id}/groups", response_model=Envelope[list[FormFieldGroupOut]])
async def list_groups(
    step_id: uuid.UUID,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_id: Annotated[uuid.UUID | None, Depends(require_form_scope("form-builder:view"))],
) -> JSONResponse:
    step = await service.get_step(tenant_db, step_id)
    _ensure_in_scope(step.branch_id, branch_id)
    fields = (await service.list_fields_for_steps(tenant_db, [step])).get(step.id, [])
    groups = (await service.list_groups_for_steps(tenant_db, [step])).get(step.id, [])
    return success_response(
        data=[_group_out(g, fields) for g in sorted(groups, key=lambda x: x.order_index)]
    )


@router.post(
    "/steps/{step_id}/groups",
    response_model=Envelope[FormFieldGroupOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_group(
    step_id: uuid.UUID,
    payload: FormFieldGroupCreate,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_id: Annotated[uuid.UUID | None, Depends(require_form_scope("form-builder:manage"))],
    audit: Annotated[_FormAudit, Depends(_form_audit)],
) -> JSONResponse:
    step = await service.get_step(tenant_db, step_id)
    _ensure_in_scope(step.branch_id, branch_id)
    group = await service.create_group(tenant_db, step_id, payload)
    audit.record("form_group_created", "FormFieldGroup", group.id, {"key": group.key})
    return success_response(data=_group_out(group, []), status_code=status.HTTP_201_CREATED)


@router.patch("/groups/{group_id}", response_model=Envelope[FormFieldGroupOut])
async def update_group(
    group_id: uuid.UUID,
    payload: FormFieldGroupUpdate,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_id: Annotated[uuid.UUID | None, Depends(require_form_scope("form-builder:manage"))],
    audit: Annotated[_FormAudit, Depends(_form_audit)],
) -> JSONResponse:
    group = await service.get_group(tenant_db, group_id)
    step = await service.get_step(tenant_db, group.step_id)
    _ensure_in_scope(step.branch_id, branch_id)
    group = await service.update_group(tenant_db, group_id, payload)
    audit.record(
        "form_group_updated",
        "FormFieldGroup",
        group_id,
        payload.model_dump(exclude_unset=True, mode="json"),
    )
    fields = (await service.list_fields_for_steps(tenant_db, [step])).get(step.id, [])
    return success_response(data=_group_out(group, fields))


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: uuid.UUID,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_id: Annotated[uuid.UUID | None, Depends(require_form_scope("form-builder:manage"))],
    audit: Annotated[_FormAudit, Depends(_form_audit)],
) -> None:
    group = await service.get_group(tenant_db, group_id)
    step = await service.get_step(tenant_db, group.step_id)
    _ensure_in_scope(step.branch_id, branch_id)
    await service.delete_group(tenant_db, group_id)
    audit.record("form_group_deleted", "FormFieldGroup", group_id)


@router.post("/steps/{step_id}/groups/reorder", response_model=Envelope[list[FormFieldGroupOut]])
async def reorder_groups(
    step_id: uuid.UUID,
    payload: ReorderRequest,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_id: Annotated[uuid.UUID | None, Depends(require_form_scope("form-builder:manage"))],
    audit: Annotated[_FormAudit, Depends(_form_audit)],
) -> JSONResponse:
    step = await service.get_step(tenant_db, step_id)
    _ensure_in_scope(step.branch_id, branch_id)
    groups = await service.reorder_groups(tenant_db, step_id, payload.ordered_ids)
    audit.record(
        "form_groups_reordered",
        "FormStep",
        step_id,
        {"orderedIds": [str(i) for i in payload.ordered_ids]},
    )
    fields = (await service.list_fields_for_steps(tenant_db, [step])).get(step.id, [])
    return success_response(data=[_group_out(g, fields) for g in groups])


# --- Publish / effective form ----------------------------------------------------


@router.post("/publish", response_model=Envelope[PublishOut])
async def publish(
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    user: Annotated[User, Depends(get_current_user)],
    branch_id: Annotated[uuid.UUID | None, Depends(require_form_scope("form-builder:manage"))],
) -> JSONResponse:
    version = await service.publish(
        tenant_db, redis, tenant_id=tenant.id, branch_id=branch_id, actor_user_id=user.id
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="form_config_published",
        entity_type="FormConfigVersion",
        entity_id=version.id,
        diff={"branchId": str(branch_id) if branch_id else None, "version": version.version},
    )
    return success_response(
        data=PublishOut(
            branch_id=branch_id, version=version.version, published_at=version.published_at
        )
    )


@router.get("/effective", response_model=Envelope[list[FormStepOut]])
@limiter.limit("120/minute")
async def get_effective_form_public(
    request: Request,
    tenant: Annotated[Tenant, Depends(public_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(public_tenant_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    branch_id: Annotated[uuid.UUID | None, Depends(public_optional_branch_id)],
) -> JSONResponse:
    """Not permission-gated — see specs/form-builder/spec.md "Form Builder
    Access Is Permission-Gated": resolving the *effective* (published) form
    is what the public visitor-request page and the staff wizard both need
    to render, neither of which necessarily holds an admin permission.
    """
    snapshot = await service.resolve_effective_form(
        tenant_db, redis, tenant_id=tenant.id, branch_id=branch_id
    )
    return success_response(data=snapshot)
