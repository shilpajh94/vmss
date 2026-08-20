import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.repository import RoleRepository
from vmss_api.core.schemas import SortOrder
from vmss_api.visitors.models import ApprovalWorkflowRule, VisitorCategory
from vmss_api.visitors.repository import ApprovalWorkflowRuleRepository, VisitorCategoryRepository
from vmss_api.visitors.schemas import (
    ApprovalWorkflowRuleCreate,
    ApprovalWorkflowRuleUpdate,
    VisitorCategoryCreate,
    VisitorCategoryUpdate,
)


async def _commit_or_conflict(tenant_db: AsyncSession, conflict_detail: str) -> None:
    """Commits, translating a residual check-then-insert race on one of the
    partial unique indexes (`models.py`'s `_NOT_DELETED` indexes; see
    `openspec/changes/harden-visitor-types-crud/design.md` Decision 2) into
    the same 409 the pre-check already raises for the common case, instead
    of an unhandled `IntegrityError` reaching the client — mirroring
    `org_structure/service.py`'s identical helper.
    """
    try:
        await tenant_db.commit()
    except IntegrityError as exc:
        await tenant_db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=conflict_detail) from exc


# --- Visitor Category -----------------------------------------------------


async def create_visitor_category(
    tenant_db: AsyncSession, payload: VisitorCategoryCreate
) -> VisitorCategory:
    repo = VisitorCategoryRepository(tenant_db)
    if await repo.get_by_code(payload.code) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Category code already exists")
    if await repo.get_by_name(payload.name) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Category name already exists")
    category = VisitorCategory(
        id=uuid.uuid4(),
        name=payload.name,
        code=payload.code,
        description=payload.description,
        form_schema=[f.model_dump(mode="json") for f in payload.form_schema],
        badge_color=payload.badge_color,
        nda_requirement=payload.nda_requirement.value if payload.nda_requirement else None,
        escort_requirement=(
            payload.escort_requirement.value if payload.escort_requirement else None
        ),
        max_duration_minutes=payload.max_duration_minutes,
    )
    tenant_db.add(category)
    await _commit_or_conflict(tenant_db, "Category name or code already exists")
    await tenant_db.refresh(category)
    return category


async def list_visitor_categories_page(
    tenant_db: AsyncSession,
    *,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: SortOrder,
) -> tuple[list[VisitorCategory], int]:
    return await VisitorCategoryRepository(tenant_db).list_page(
        page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
    )


async def get_visitor_category(tenant_db: AsyncSession, category_id: uuid.UUID) -> VisitorCategory:
    category = await VisitorCategoryRepository(tenant_db).get(category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Visitor category not found")
    return category


async def update_visitor_category(
    tenant_db: AsyncSession, category_id: uuid.UUID, payload: VisitorCategoryUpdate
) -> VisitorCategory:
    repo = VisitorCategoryRepository(tenant_db)
    category = await get_visitor_category(tenant_db, category_id)
    changes = payload.model_dump(exclude_unset=True, mode="json")
    new_code = changes.get("code")
    if (
        new_code is not None
        and new_code != category.code
        and await repo.get_by_code(new_code) is not None
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Category code already exists")
    new_name = changes.get("name")
    if (
        new_name is not None
        and new_name != category.name
        and await repo.get_by_name(new_name) is not None
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Category name already exists")
    for field, value in changes.items():
        setattr(category, field, value)
    await _commit_or_conflict(tenant_db, "Category name or code already exists")
    await tenant_db.refresh(category)
    return category


async def delete_visitor_category(tenant_db: AsyncSession, category_id: uuid.UUID) -> None:
    repo = VisitorCategoryRepository(tenant_db)
    category = await get_visitor_category(tenant_db, category_id)
    await repo.soft_delete(category)
    await tenant_db.commit()


# --- Approval Workflow Rule -------------------------------------------------


async def create_approval_workflow_rule(
    tenant_db: AsyncSession, payload: ApprovalWorkflowRuleCreate
) -> ApprovalWorkflowRule:
    if await VisitorCategoryRepository(tenant_db).get(payload.visitor_category_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Visitor category not found")
    if await RoleRepository(tenant_db).get(payload.approver_role_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Approver role not found")
    repo = ApprovalWorkflowRuleRepository(tenant_db)
    if (
        await repo.get_by_category_and_step(payload.visitor_category_id, payload.step_order)
        is not None
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Step order already used for this category"
        )
    rule = ApprovalWorkflowRule(id=uuid.uuid4(), **payload.model_dump())
    tenant_db.add(rule)
    await _commit_or_conflict(tenant_db, "Step order already used for this category")
    await tenant_db.refresh(rule)
    return rule


async def list_approval_workflow_rules_page(
    tenant_db: AsyncSession,
    *,
    visitor_category_id: uuid.UUID | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: SortOrder,
) -> tuple[list[ApprovalWorkflowRule], int]:
    return await ApprovalWorkflowRuleRepository(tenant_db).list_page(
        visitor_category_id=visitor_category_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def get_approval_workflow_rule(
    tenant_db: AsyncSession, rule_id: uuid.UUID
) -> ApprovalWorkflowRule:
    rule = await ApprovalWorkflowRuleRepository(tenant_db).get(rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Approval workflow rule not found")
    return rule


async def update_approval_workflow_rule(
    tenant_db: AsyncSession, rule_id: uuid.UUID, payload: ApprovalWorkflowRuleUpdate
) -> ApprovalWorkflowRule:
    repo = ApprovalWorkflowRuleRepository(tenant_db)
    rule = await get_approval_workflow_rule(tenant_db, rule_id)
    changes = payload.model_dump(exclude_unset=True)
    new_role_id = changes.get("approver_role_id")
    if new_role_id is not None and await RoleRepository(tenant_db).get(new_role_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Approver role not found")
    new_step = changes.get("step_order")
    if (
        new_step is not None
        and new_step != rule.step_order
        and await repo.get_by_category_and_step(rule.visitor_category_id, new_step) is not None
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Step order already used for this category"
        )
    for field, value in changes.items():
        setattr(rule, field, value)
    await _commit_or_conflict(tenant_db, "Step order already used for this category")
    await tenant_db.refresh(rule)
    return rule


async def delete_approval_workflow_rule(tenant_db: AsyncSession, rule_id: uuid.UUID) -> None:
    repo = ApprovalWorkflowRuleRepository(tenant_db)
    rule = await get_approval_workflow_rule(tenant_db, rule_id)
    await repo.soft_delete(rule)
    await tenant_db.commit()
