import uuid
from collections.abc import Collection
from typing import Any

from sqlalchemy import select

from vmss_api.core.database import TenantScopedRepository, order_clause
from vmss_api.core.schemas import SortOrder
from vmss_api.visitors.models import ApprovalWorkflowRule, VisitorCategory
from vmss_api.visitors.schemas import (
    ApprovalWorkflowRuleStatus,
    EscortRequirement,
    NdaRequirement,
)


class VisitorCategoryRepository(TenantScopedRepository[VisitorCategory]):
    model = VisitorCategory

    async def get_active(self, id_: uuid.UUID) -> VisitorCategory | None:
        """Used to validate `visitorCategoryId` on invitation creation — an
        id must resolve to an *active* category, not merely a non-deleted
        one (invitation-multi-step-approval spec.md "Unknown, inactive, or
        cross-tenant visitor category is rejected"). Same posture as
        `visit_info.repository.VisitPurposeRepository.get_active`.
        """
        stmt = select(VisitorCategory).where(
            VisitorCategory.id == id_,
            VisitorCategory.is_active.is_(True),
            VisitorCategory.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, code: str) -> VisitorCategory | None:
        stmt = select(VisitorCategory).where(
            VisitorCategory.code == code, VisitorCategory.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_name(self, name: str) -> VisitorCategory | None:
        stmt = select(VisitorCategory).where(
            VisitorCategory.name == name, VisitorCategory.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_existing_codes(self, codes: Collection[str]) -> set[str]:
        """Batch lookup for `service.py::bulk_create_visitor_categories` —
        one `WHERE code IN (...)` for the whole requested batch, instead of
        one `get_by_code` call per name. See query-performance.md §2.
        """
        if not codes:
            return set()
        stmt = select(VisitorCategory.code).where(
            VisitorCategory.code.in_(codes), VisitorCategory.deleted_at.is_(None)
        )
        return set((await self.session.execute(stmt)).scalars().all())

    async def get_existing_names(self, names: Collection[str]) -> set[str]:
        """Batch counterpart of `get_existing_codes` for names."""
        if not names:
            return set()
        stmt = select(VisitorCategory.name).where(
            VisitorCategory.name.in_(names), VisitorCategory.deleted_at.is_(None)
        )
        return set((await self.session.execute(stmt)).scalars().all())

    async def list_by_ids(self, ids: Collection[uuid.UUID]) -> list[VisitorCategory]:
        """Batch re-fetch for `service.py::bulk_create_visitor_categories`,
        used once after a bulk-insert commit to pick up server-generated
        timestamp columns for every created row in one query instead of one
        `session.refresh()` per row.
        """
        if not ids:
            return []
        stmt = select(VisitorCategory).where(
            VisitorCategory.id.in_(ids), VisitorCategory.deleted_at.is_(None)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_page(
        self,
        *,
        badge_color: str | None,
        nda_requirement: NdaRequirement | None,
        escort_requirement: EscortRequirement | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[VisitorCategory], int]:
        column = {"name": VisitorCategory.name, "created_at": VisitorCategory.created_at}[sort_by]
        filters: list[Any] = []
        if badge_color is not None:
            filters.append(VisitorCategory.badge_color == badge_color)
        if nda_requirement is not None:
            filters.append(VisitorCategory.nda_requirement == nda_requirement.value)
        if escort_requirement is not None:
            filters.append(VisitorCategory.escort_requirement == escort_requirement.value)
        return await super().paginate(
            page=page,
            page_size=page_size,
            order_by=order_clause(column, sort_order),
            filters=filters,
        )


class ApprovalWorkflowRuleRepository(TenantScopedRepository[ApprovalWorkflowRule]):
    model = ApprovalWorkflowRule

    async def list_active_for_category(
        self, visitor_category_id: uuid.UUID
    ) -> list[ApprovalWorkflowRule]:
        """Every active rule for one category, ordered by `step_order` —
        backs the invitation-submission snapshot
        (invitation-multi-step-approval spec.md "Submission Snapshots the
        Category's Active Workflow Into Ordered Steps"). An empty result
        means the category has no configured workflow.
        """
        stmt = (
            select(ApprovalWorkflowRule)
            .where(
                ApprovalWorkflowRule.visitor_category_id == visitor_category_id,
                ApprovalWorkflowRule.is_active.is_(True),
                ApprovalWorkflowRule.deleted_at.is_(None),
            )
            .order_by(ApprovalWorkflowRule.step_order.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_category_and_step(
        self, visitor_category_id: uuid.UUID, step_order: int
    ) -> ApprovalWorkflowRule | None:
        stmt = select(ApprovalWorkflowRule).where(
            ApprovalWorkflowRule.visitor_category_id == visitor_category_id,
            ApprovalWorkflowRule.step_order == step_order,
            ApprovalWorkflowRule.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        visitor_category_id: uuid.UUID | None,
        status: ApprovalWorkflowRuleStatus | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[ApprovalWorkflowRule], int]:
        column = {
            "step_order": ApprovalWorkflowRule.step_order,
            "created_at": ApprovalWorkflowRule.created_at,
        }[sort_by]
        filters: list[Any] = []
        if visitor_category_id is not None:
            filters.append(ApprovalWorkflowRule.visitor_category_id == visitor_category_id)
        if status is not None:
            filters.append(
                ApprovalWorkflowRule.is_active.is_(status == ApprovalWorkflowRuleStatus.active)
            )
        return await super().paginate(
            page=page,
            page_size=page_size,
            order_by=order_clause(column, sort_order),
            filters=filters,
        )
