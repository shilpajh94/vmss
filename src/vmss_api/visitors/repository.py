import uuid
from typing import Any

from sqlalchemy import select

from vmss_api.core.database import TenantScopedRepository
from vmss_api.core.schemas import SortOrder
from vmss_api.visitors.models import ApprovalWorkflowRule, VisitorCategory


def _order_clause(column: Any, sort_order: SortOrder) -> Any:
    return column.desc() if sort_order == SortOrder.desc else column.asc()


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

    async def list_page(
        self, *, page: int, page_size: int, sort_by: str, sort_order: SortOrder
    ) -> tuple[list[VisitorCategory], int]:
        column = {"name": VisitorCategory.name, "created_at": VisitorCategory.created_at}[sort_by]
        return await super().paginate(
            page=page, page_size=page_size, order_by=_order_clause(column, sort_order)
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
        return await super().paginate(
            page=page,
            page_size=page_size,
            order_by=_order_clause(column, sort_order),
            filters=filters,
        )
