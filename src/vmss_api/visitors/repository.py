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
