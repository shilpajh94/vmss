import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.schemas import BranchScope, SortOrder
from vmss_api.core.tenancy import branch_filter as _core_branch_filter
from vmss_api.invitations.models import Invitation
from vmss_api.invitations.repository import relevant_to_me_clause

_CHECKED_IN_STATUSES = ("checked_in", "checked_out")
# A visit "happening today" — denied/archived/still-pending ones aren't.
_VISIT_TODAY_STATUSES = ("approved", "checked_in", "checked_out")


def _branch_filter(branch_scope: BranchScope) -> Any | None:
    """`Invitation.branch_id`-bound wrapper around the shared
    `core.tenancy.branch_filter`.
    """
    return _core_branch_filter(Invitation.branch_id, branch_scope)


def _order_clause(column: Any, sort_order: SortOrder) -> Any:
    return column.desc() if sort_order == SortOrder.desc else column.asc()


def _upcoming_filters(now_utc: datetime) -> tuple[Any, ...]:
    """Approved, never admitted, not yet expired."""
    return (
        Invitation.status == "approved",
        Invitation.check_in_status == "unused",
        Invitation.expires_at > now_utc,
    )


class DashboardRepository:
    """Read-only queries over `invitations.models.Invitation` for the
    `dashboard` capability — owns no table of its own, same posture as
    `reports/repository.py::BranchRollupRepository` (design.md Decision 1).
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def overview_counts(
        self,
        branch_scope: BranchScope,
        *,
        day_start_utc: datetime,
        day_end_utc: datetime,
        now_utc: datetime,
    ) -> dict[str, int]:
        """One filtered count query per card — never a per-row Python loop
        (query-performance.md §2).
        """
        branch_filter = _branch_filter(branch_scope)
        base_filters: list[Any] = [Invitation.deleted_at.is_(None)]
        if branch_filter is not None:
            base_filters.append(branch_filter)

        async def _count(*extra_filters: Any) -> int:
            stmt = select(func.count()).select_from(Invitation).where(*base_filters, *extra_filters)
            return (await self.session.execute(stmt)).scalar_one()

        return {
            "visits_today_count": await _count(
                Invitation.created_at >= day_start_utc, Invitation.created_at < day_end_utc
            ),
            "checked_in_count": await _count(Invitation.status == "checked_in"),
            "pending_approval_count": await _count(Invitation.status == "submitted"),
            "upcoming_visitor_count": await _count(
                Invitation.status == "approved", Invitation.expires_at > now_utc
            ),
        }

    async def upcoming_visitors_preview(
        self, branch_scope: BranchScope, *, now_utc: datetime, limit: int
    ) -> list[Invitation]:
        """`approved`, non-expired invitations ordered soonest-expiry first,
        capped at `limit` (design.md Decision 6 — bounded, not paginated).
        """
        branch_filter = _branch_filter(branch_scope)
        filters: list[Any] = [
            Invitation.deleted_at.is_(None),
            Invitation.status == "approved",
            Invitation.expires_at > now_utc,
        ]
        if branch_filter is not None:
            filters.append(branch_filter)
        stmt = select(Invitation).where(*filters).order_by(Invitation.expires_at.asc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def personal_overview_counts(
        self,
        *,
        user_id: uuid.UUID,
        default_host_role_id: uuid.UUID,
        today: date,
        now_utc: datetime,
    ) -> dict[str, int]:
        """dashboard spec "Personal Dashboard Overview Scoped to the Caller's
        Relevant Invitations" — every figure in one `COUNT(*) FILTER (...)`
        query over the caller's `relevantToMe` set.
        """
        stmt = select(
            func.count()
            .filter(
                Invitation.preferred_visit_date == today,
                Invitation.status.in_(_VISIT_TODAY_STATUSES),
            )
            .label("visits_today"),
            func.count().filter(Invitation.status == "checked_in").label("inside_now"),
            func.count().filter(Invitation.status == "submitted").label("awaiting_approval"),
            func.count().filter(*_upcoming_filters(now_utc)).label("upcoming"),
        ).where(
            Invitation.deleted_at.is_(None),
            relevant_to_me_clause(user_id, default_host_role_id),
        )
        return dict((await self.session.execute(stmt)).one()._mapping)

    async def personal_upcoming_preview(
        self,
        *,
        user_id: uuid.UUID,
        default_host_role_id: uuid.UUID,
        now_utc: datetime,
        limit: int,
    ) -> list[Invitation]:
        stmt = (
            select(Invitation)
            .where(
                Invitation.deleted_at.is_(None),
                relevant_to_me_clause(user_id, default_host_role_id),
                *_upcoming_filters(now_utc),
            )
            .order_by(
                Invitation.preferred_visit_date.asc().nulls_last(),
                Invitation.preferred_visit_time.asc().nulls_last(),
                Invitation.expires_at.asc(),
            )
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def paginated_checkins(
        self,
        branch_scope: BranchScope,
        *,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[Invitation], int]:
        """Every invitation that has been checked in at least once (status
        `checked_in` or `checked_out`) — one count query plus one page
        query, same shape as `invitations/repository.py`'s `list_page`.
        """
        branch_filter = _branch_filter(branch_scope)
        filters: list[Any] = [
            Invitation.deleted_at.is_(None),
            Invitation.status.in_(_CHECKED_IN_STATUSES),
        ]
        if branch_filter is not None:
            filters.append(branch_filter)
        column = {
            "checked_in_at": Invitation.checked_in_at,
            "checked_out_at": Invitation.checked_out_at,
        }[sort_by]

        total_stmt = select(func.count()).select_from(Invitation).where(*filters)
        total = (await self.session.execute(total_stmt)).scalar_one()

        stmt = (
            select(Invitation)
            .where(*filters)
            .order_by(_order_clause(column, sort_order))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        return rows, total

    async def search_by_contact_name(
        self, branch_scope: BranchScope, *, query: str, limit: int
    ) -> list[Invitation]:
        """Case-insensitive partial match on `primary_contact_full_name`,
        capped at `limit` — no full-text/fuzzy search (design.md Non-Goals).
        """
        branch_filter = _branch_filter(branch_scope)
        filters: list[Any] = [
            Invitation.deleted_at.is_(None),
            Invitation.primary_contact_full_name.ilike(f"%{query}%"),
        ]
        if branch_filter is not None:
            filters.append(branch_filter)
        stmt = (
            select(Invitation)
            .where(*filters)
            .order_by(Invitation.primary_contact_full_name.asc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())
