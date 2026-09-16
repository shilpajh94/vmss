import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.audit import record_audit_log
from vmss_api.auth.models import User
from vmss_api.core.deps import (
    get_current_user,
    get_pagination,
    get_tenant,
    get_tenant_db,
    require_permission,
)
from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import paginated_response, success_response
from vmss_api.core.schemas import Envelope, PaginatedEnvelope, SortOrder
from vmss_api.tenant.models import Tenant
from vmss_api.visitors import service
from vmss_api.visitors.deps import public_tenant_db
from vmss_api.visitors.schemas import (
    ApprovalWorkflowRuleCreate,
    ApprovalWorkflowRuleOut,
    ApprovalWorkflowRuleSortableField,
    ApprovalWorkflowRuleStatus,
    ApprovalWorkflowRuleUpdate,
    EscortRequirement,
    NdaRequirement,
    VisitorCategoryCreate,
    VisitorCategoryOut,
    VisitorCategorySortableField,
    VisitorCategoryUpdate,
)

router = APIRouter(tags=["visitor-types"])

category_router = APIRouter(prefix="/visitor-categories")
workflow_rule_router = APIRouter(prefix="/approval-workflow-rules")


def _queue_audit(
    background_tasks: BackgroundTasks,
    tenant: Tenant,
    user: User,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
) -> None:
    """Queues one `AuditLog` write (security-architecture.md §5) as a
    background task so it never blocks the response — see `auth/audit.py`.
    """
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
    )


# --- Visitor Category -----------------------------------------------------
#
# Tenant-wide, not branch-scoped: a visitor category and its form schema
# apply across the whole company, same posture as org_structure's
# Company/Branch CRUD.


@category_router.post(
    "",
    response_model=Envelope[VisitorCategoryOut],
    dependencies=[Depends(require_permission("visitor-categories:manage"))],
    status_code=status.HTTP_201_CREATED,
)
async def create_visitor_category(
    payload: VisitorCategoryCreate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    category = await service.create_visitor_category(tenant_db, payload)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="visitor_category_created",
        entity_type="VisitorCategory",
        entity_id=category.id,
    )
    return success_response(
        data=VisitorCategoryOut.model_validate(category), status_code=status.HTTP_201_CREATED
    )


@category_router.get(
    "",
    response_model=PaginatedEnvelope[VisitorCategoryOut],
)
@limiter.limit("60/minute")
async def list_visitor_categories(
    request: Request,
    tenant_db: Annotated[AsyncSession, Depends(public_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    badge_color: Annotated[str | None, Query(alias="badgeColor")] = None,
    nda_requirement: Annotated[NdaRequirement | None, Query(alias="ndaRequirement")] = None,
    escort_requirement: Annotated[
        EscortRequirement | None, Query(alias="escortRequirement")
    ] = None,
    sort_by: Annotated[VisitorCategorySortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    """Public — no bearer token, no permission check
    (security-architecture.md §2's public-endpoint posture, same rationale
    as `org_structure/router.py::list_branches`): the pre-registration form
    needs to render a category picker before a visitor authenticates.
    """
    page, page_size = pagination
    categories, total = await service.list_visitor_categories_page(
        tenant_db,
        badge_color=badge_color,
        nda_requirement=nda_requirement,
        escort_requirement=escort_requirement,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return paginated_response(
        data=[VisitorCategoryOut.model_validate(c) for c in categories],
        page=page,
        page_size=page_size,
        total=total,
    )


@category_router.get(
    "/{category_id}",
    response_model=Envelope[VisitorCategoryOut],
    dependencies=[Depends(require_permission("visitor-categories:view"))],
)
async def get_visitor_category(
    category_id: uuid.UUID, tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)]
) -> JSONResponse:
    category = await service.get_visitor_category(tenant_db, category_id)
    return success_response(data=VisitorCategoryOut.model_validate(category))


@category_router.put(
    "/{category_id}",
    response_model=Envelope[VisitorCategoryOut],
    dependencies=[Depends(require_permission("visitor-categories:manage"))],
)
async def update_visitor_category(
    category_id: uuid.UUID,
    payload: VisitorCategoryUpdate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    category = await service.update_visitor_category(tenant_db, category_id, payload)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="visitor_category_updated",
        entity_type="VisitorCategory",
        entity_id=category.id,
    )
    return success_response(data=VisitorCategoryOut.model_validate(category))


@category_router.delete(
    "/{category_id}",
    dependencies=[Depends(require_permission("visitor-categories:manage"))],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_visitor_category(
    category_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete_visitor_category(tenant_db, category_id)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="visitor_category_deleted",
        entity_type="VisitorCategory",
        entity_id=category_id,
    )


# --- Approval Workflow Rule -------------------------------------------------
#
# Tenant-wide, not branch-scoped — see Visitor Category above. Configuration
# only: evaluating these rules against an actual visit is the (not-yet-built)
# `approvals` feature's job.


@workflow_rule_router.post(
    "",
    response_model=Envelope[ApprovalWorkflowRuleOut],
    dependencies=[Depends(require_permission("approval-workflow-rules:manage"))],
    status_code=status.HTTP_201_CREATED,
)
async def create_approval_workflow_rule(
    payload: ApprovalWorkflowRuleCreate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    rule = await service.create_approval_workflow_rule(tenant_db, payload)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="approval_workflow_rule_created",
        entity_type="ApprovalWorkflowRule",
        entity_id=rule.id,
    )
    return success_response(
        data=ApprovalWorkflowRuleOut.model_validate(rule), status_code=status.HTTP_201_CREATED
    )


@workflow_rule_router.get(
    "",
    response_model=PaginatedEnvelope[ApprovalWorkflowRuleOut],
    dependencies=[Depends(require_permission("approval-workflow-rules:view"))],
)
async def list_approval_workflow_rules(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    visitor_category_id: Annotated[uuid.UUID | None, Query(alias="visitorCategoryId")] = None,
    rule_status: Annotated[ApprovalWorkflowRuleStatus | None, Query(alias="status")] = None,
    sort_by: Annotated[ApprovalWorkflowRuleSortableField, Query(alias="sortBy")] = "step_order",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    page, page_size = pagination
    rules, total = await service.list_approval_workflow_rules_page(
        tenant_db,
        visitor_category_id=visitor_category_id,
        status=rule_status,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return paginated_response(
        data=[ApprovalWorkflowRuleOut.model_validate(r) for r in rules],
        page=page,
        page_size=page_size,
        total=total,
    )


@workflow_rule_router.get(
    "/{rule_id}",
    response_model=Envelope[ApprovalWorkflowRuleOut],
    dependencies=[Depends(require_permission("approval-workflow-rules:view"))],
)
async def get_approval_workflow_rule(
    rule_id: uuid.UUID, tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)]
) -> JSONResponse:
    rule = await service.get_approval_workflow_rule(tenant_db, rule_id)
    return success_response(data=ApprovalWorkflowRuleOut.model_validate(rule))


@workflow_rule_router.put(
    "/{rule_id}",
    response_model=Envelope[ApprovalWorkflowRuleOut],
    dependencies=[Depends(require_permission("approval-workflow-rules:manage"))],
)
async def update_approval_workflow_rule(
    rule_id: uuid.UUID,
    payload: ApprovalWorkflowRuleUpdate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    rule = await service.update_approval_workflow_rule(tenant_db, rule_id, payload)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="approval_workflow_rule_updated",
        entity_type="ApprovalWorkflowRule",
        entity_id=rule.id,
    )
    return success_response(data=ApprovalWorkflowRuleOut.model_validate(rule))


@workflow_rule_router.delete(
    "/{rule_id}",
    dependencies=[Depends(require_permission("approval-workflow-rules:manage"))],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_approval_workflow_rule(
    rule_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete_approval_workflow_rule(tenant_db, rule_id)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="approval_workflow_rule_deleted",
        entity_type="ApprovalWorkflowRule",
        entity_id=rule_id,
    )


router.include_router(category_router)
router.include_router(workflow_rule_router)
