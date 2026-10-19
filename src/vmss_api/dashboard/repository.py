import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, cast, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.schemas import BranchScope, SortOrder
from vmss_api.core.tenancy import branch_filter as _core_branch_filter
from vmss_api.invitations.models import Invitation
from vmss_api.invitations.repository import relevant_to_me_clause
from vmss_api.org_structure.models import Department
from vmss_api.visit_info.models import VisitPurpose

_CHECKED_IN_STATUSES = ("checked_in", "checked_out")
# A visit "happening today" — denied/archived/still-pending ones aren't.
_VISIT_TODAY_STATUSES = ("approved", "checked_in", "checked_out")
# A "scheduled visit" for analytics: everything that was approved for its
# date, including no-shows the sweep has since archived (design.md Context —
# `archived` is reached only from approved-and-never-admitted).
_SCHEDULED_STATUSES = ("approved", "checked_in", "checked_out", "archived")
BREAKDOWN_STATUSES = ("submitted", "approved", "checked_in", "checked_out", "denied", "archived")


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

    @staticmethod
    def branch_scope_clause(branch_scope: BranchScope) -> Any | None:
        return _branch_filter(branch_scope)

    @staticmethod
    def personal_scope_clause(user_id: uuid.UUID, default_host_role_id: uuid.UUID) -> Any:
        return relevant_to_me_clause(user_id, default_host_role_id)

    @staticmethod
    def _scoped(scope_clause: Any | None) -> list[Any]:
        """Soft-delete filter plus the caller's scope — either a branch
        filter (None meaning every branch) or `relevant_to_me_clause`.
        """
        filters: list[Any] = [Invitation.deleted_at.is_(None)]
        if scope_clause is not None:
            filters.append(scope_clause)
        return filters

    async def overview_counts(
        self,
        branch_scope: BranchScope,
        *,
        today: date,
        day_start_utc: datetime,
        day_end_utc: datetime,
        now_utc: datetime,
    ) -> dict[str, Any]:
        """Every KPI figure in one `COUNT(*) FILTER (...)` statement, same
        shape as `personal_overview_counts` (query-performance.md §2).
        `upcoming_visitor_count` shares `_upcoming_filters` with the preview
        list so the two can't disagree.
        """
        stmt = select(
            func.count()
            .filter(Invitation.created_at >= day_start_utc, Invitation.created_at < day_end_utc)
            .label("visits_today_count"),
            func.count()
            .filter(
                Invitation.preferred_visit_date == today,
                Invitation.status.in_(_VISIT_TODAY_STATUSES),
            )
            .label("scheduled_today_count"),
            func.count()
            .filter(
                Invitation.checked_in_at >= day_start_utc, Invitation.checked_in_at < day_end_utc
            )
            .label("checked_in_today_count"),
            func.count().filter(Invitation.status == "checked_in").label("checked_in_count"),
            func.count().filter(Invitation.status == "submitted").label("pending_approval_count"),
            func.min(func.coalesce(Invitation.submitted_at, Invitation.created_at))
            .filter(Invitation.status == "submitted")
            .label("oldest_pending_submitted_at"),
            func.count().filter(*_upcoming_filters(now_utc)).label("upcoming_visitor_count"),
        ).where(*self._scoped(_branch_filter(branch_scope)))
        return dict((await self.session.execute(stmt)).one()._mapping)

    async def upcoming_visitors_preview(
        self, branch_scope: BranchScope, *, now_utc: datetime, limit: int
    ) -> list[tuple[Invitation, str | None]]:
        """`approved`, never-admitted, non-expired invitations ordered
        soonest-expiry first, capped at `limit` (design.md Decision 6 —
        bounded, not paginated), each paired with its host's full name
        from one outer join (live-dashboards-and-analytics design.md D5).
        """
        stmt = (
            select(Invitation, User.full_name)
            .outerjoin(User, User.id == Invitation.host_id)
            .where(*self._scoped(_branch_filter(branch_scope)), *_upcoming_filters(now_utc))
            .order_by(Invitation.expires_at.asc())
            .limit(limit)
        )
        return [(row[0], row[1]) for row in (await self.session.execute(stmt)).all()]

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
    ) -> tuple[list[tuple[Invitation, str | None]], int]:
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
            select(Invitation, User.full_name)
            .outerjoin(User, User.id == Invitation.host_id)
            .where(*filters)
            .order_by(_order_clause(column, sort_order))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = [(row[0], row[1]) for row in (await self.session.execute(stmt)).all()]
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

    # --- Analytics (live-dashboards-and-analytics design.md D3) ----------
    # Each takes `scope_clause`: the branch filter for the branch-wide
    # endpoint, `relevant_to_me_clause` for the personal one. Zero-filling
    # missing days/hours/statuses is the service's job.

    async def daily_trend(
        self, scope_clause: Any | None, *, start: date, end: date
    ) -> list[tuple[date, int, int, int]]:
        stmt = (
            select(
                Invitation.preferred_visit_date,
                func.count(),
                func.count().filter(Invitation.checked_in_at.is_not(None)),
                func.count().filter(Invitation.status == "archived"),
            )
            .where(
                *self._scoped(scope_clause),
                Invitation.status.in_(_SCHEDULED_STATUSES),
                Invitation.preferred_visit_date >= start,
                Invitation.preferred_visit_date <= end,
            )
            .group_by(Invitation.preferred_visit_date)
        )
        return [(r[0], r[1], r[2], r[3]) for r in (await self.session.execute(stmt)).all()]

    async def hourly_check_ins(
        self,
        scope_clause: Any | None,
        *,
        timezone: str,
        day_start_utc: datetime,
        day_end_utc: datetime,
    ) -> list[tuple[int, int]]:
        hour = extract("hour", func.timezone(timezone, Invitation.checked_in_at))
        stmt = (
            select(hour, func.count())
            .where(
                *self._scoped(scope_clause),
                Invitation.checked_in_at >= day_start_utc,
                Invitation.checked_in_at < day_end_utc,
            )
            .group_by(hour)
        )
        return [(int(r[0]), r[1]) for r in (await self.session.execute(stmt)).all()]

    async def status_breakdown(
        self, scope_clause: Any | None, *, timezone: str, start: date, end: date
    ) -> list[tuple[str, int]]:
        """Dated by the scheduled visit date, falling back to the tenant-local
        creation date for an invitation that has none.
        """
        visit_day = func.coalesce(
            Invitation.preferred_visit_date,
            cast(func.timezone(timezone, Invitation.created_at), Date),
        )
        stmt = (
            select(Invitation.status, func.count())
            .where(
                *self._scoped(scope_clause),
                Invitation.status.in_(BREAKDOWN_STATUSES),
                visit_day >= start,
                visit_day <= end,
            )
            .group_by(Invitation.status)
        )
        return [(r[0], r[1]) for r in (await self.session.execute(stmt)).all()]

    async def top_purposes(
        self, scope_clause: Any | None, *, start: date, end: date
    ) -> list[tuple[str | None, int]]:
        return await self._label_counts(
            scope_clause,
            start=start,
            end=end,
            configured_name=VisitPurpose.name,
            free_text=Invitation.purpose_of_visit,
            join_target=VisitPurpose,
            join_on=VisitPurpose.id == Invitation.purpose_id,
        )

    async def top_departments(
        self, scope_clause: Any | None, *, start: date, end: date
    ) -> list[tuple[str | None, int]]:
        return await self._label_counts(
            scope_clause,
            start=start,
            end=end,
            configured_name=Department.name,
            free_text=Invitation.department_to_visit,
            join_target=Department,
            join_on=Department.id == Invitation.department_id,
        )

    async def _label_counts(
        self,
        scope_clause: Any | None,
        *,
        start: date,
        end: date,
        configured_name: Any,
        free_text: Any,
        join_target: Any,
        join_on: Any,
    ) -> list[tuple[str | None, int]]:
        """Scheduled visits per label: the configured name, else the
        free-text value grouped case-insensitively (displayed as its first
        spelling byte-wise, so "Meeting" wins over "meeting"), else NULL
        for the service to render as "Not specified". Every label is
        returned — one row per distinct label, so the top-5/Other cut
        happens in Python.
        """
        display = func.coalesce(configured_name, func.nullif(func.trim(free_text), ""))
        key = func.lower(display)
        stmt = (
            # "C" collation: the displayed spelling is chosen byte-wise, so
            # it doesn't depend on the database's locale.
            select(func.min(display.collate("C")), func.count())
            .select_from(Invitation)
            .outerjoin(join_target, join_on)
            .where(
                *self._scoped(scope_clause),
                Invitation.status.in_(_SCHEDULED_STATUSES),
                Invitation.preferred_visit_date >= start,
                Invitation.preferred_visit_date <= end,
            )
            .group_by(key)
        )
        return [(r[0], r[1]) for r in (await self.session.execute(stmt)).all()]
