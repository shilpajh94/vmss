import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.rbac_catalog import NON_WORKFLOW_STEP_ROLE_NAMES
from vmss_api.auth.repository import RoleRepository
from vmss_api.core.schemas import SortOrder
from vmss_api.visitors.models import ApprovalWorkflowRule, VisitorCategory
from vmss_api.visitors.repository import ApprovalWorkflowRuleRepository, VisitorCategoryRepository
from vmss_api.visitors.schemas import (
    ApprovalWorkflowRuleCreate,
    ApprovalWorkflowRuleStatus,
    ApprovalWorkflowRuleUpdate,
    EscortRequirement,
    NdaRequirement,
    VisitorCategoryBulkCreate,
    VisitorCategoryBulkCreateItem,
    VisitorCategoryBulkCreateItemStatus,
    VisitorCategoryBulkCreateOut,
    VisitorCategoryCreate,
    VisitorCategoryOut,
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


def _slugify(name: str) -> str:
    """Derives a `code` from a category `name` for the bulk-create path,
    which only collects names — same algorithm as `AddFieldModal.tsx`'s
    `slugify` (VMMS_WEB), reimplemented here since bulk-create has no
    client-side counterpart to run it in.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    return slug.strip("_")


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


async def bulk_create_visitor_categories(
    tenant_db: AsyncSession, payload: VisitorCategoryBulkCreate
) -> VisitorCategoryBulkCreateOut:
    """Creates one `VisitorCategory` per name that doesn't collide with an
    existing category (by name or derived code) or with an earlier name in
    this same request — skip-and-report per name, not all-or-nothing like
    `create_visitor_category`, since a bulk paste's whole point is
    unattended batch processing (design.md's "Skip-and-report" decision).
    """
    repo = VisitorCategoryRepository(tenant_db)
    seen_names: set[str] = set()
    seen_codes: set[str] = set()
    # (name, status, reason, category-row-if-created) — the row is refreshed
    # and turned into a `VisitorCategoryOut` only after the batch commit
    # below, once its server-generated fields (timestamps) are populated.
    results: list[
        tuple[str, VisitorCategoryBulkCreateItemStatus, str | None, VisitorCategory | None]
    ] = []

    for raw_name in payload.names:
        name = raw_name.strip()
        if not name:
            continue

        code = _slugify(name)
        reason: str | None = None
        if name in seen_names or code in seen_codes:
            reason = "Duplicate in this request"
        elif await repo.get_by_code(code) is not None:
            reason = "Category code already exists"
        elif await repo.get_by_name(name) is not None:
            reason = "Category name already exists"

        seen_names.add(name)
        seen_codes.add(code)

        if reason is not None:
            results.append((name, VisitorCategoryBulkCreateItemStatus.skipped, reason, None))
            continue

        category = VisitorCategory(id=uuid.uuid4(), name=name, code=code)
        tenant_db.add(category)
        results.append((name, VisitorCategoryBulkCreateItemStatus.created, None, category))

    await _commit_or_conflict(tenant_db, "One or more categories in this batch already exist")

    items: list[VisitorCategoryBulkCreateItem] = []
    created_count = 0
    skipped_count = 0
    for name, item_status, reason, category_row in results:
        if category_row is not None:
            await tenant_db.refresh(category_row)
            items.append(
                VisitorCategoryBulkCreateItem(
                    name=name,
                    status=item_status,
                    category=VisitorCategoryOut.model_validate(category_row),
                )
            )
            created_count += 1
        else:
            items.append(
                VisitorCategoryBulkCreateItem(name=name, status=item_status, reason=reason)
            )
            skipped_count += 1

    return VisitorCategoryBulkCreateOut(
        items=items, created_count=created_count, skipped_count=skipped_count
    )


async def list_visitor_categories_page(
    tenant_db: AsyncSession,
    *,
    badge_color: str | None,
    nda_requirement: NdaRequirement | None,
    escort_requirement: EscortRequirement | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: SortOrder,
) -> tuple[list[VisitorCategory], int]:
    return await VisitorCategoryRepository(tenant_db).list_page(
        badge_color=badge_color,
        nda_requirement=nda_requirement,
        escort_requirement=escort_requirement,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
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
    approver_role = await RoleRepository(tenant_db).get(payload.approver_role_id)
    if approver_role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Approver role not found")
    if approver_role.name.lower() in NON_WORKFLOW_STEP_ROLE_NAMES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"'{approver_role.name}' cannot be a step's approver role",
        )
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
    status: ApprovalWorkflowRuleStatus | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: SortOrder,
) -> tuple[list[ApprovalWorkflowRule], int]:
    return await ApprovalWorkflowRuleRepository(tenant_db).list_page(
        visitor_category_id=visitor_category_id,
        status=status,
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
    if new_role_id is not None:
        new_role = await RoleRepository(tenant_db).get(new_role_id)
        if new_role is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Approver role not found")
        if new_role.name.lower() in NON_WORKFLOW_STEP_ROLE_NAMES:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"'{new_role.name}' cannot be a step's approver role",
            )
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
