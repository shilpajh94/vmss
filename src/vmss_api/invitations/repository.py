import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, select, update
from sqlalchemy.orm import selectinload

from vmss_api.core.database import TenantScopedRepository
from vmss_api.core.schemas import BranchScope, SortOrder
from vmss_api.invitations.models import Invitation, InvitationVehicle, InvitationVisitor


def _branch_filter(branch_scope: BranchScope) -> Any | None:
    """Same `BranchScope` -> filter-clause translation as
    `org_structure/repository.py::_branch_filter`: `None` (no filter) for a
    company-wide "all" scope, otherwise `Invitation.branch_id IN (...)`.
    """
    return None if branch_scope == "all" else Invitation.branch_id.in_(branch_scope)


def _order_clause(column: Any, sort_order: SortOrder) -> Any:
    return column.desc() if sort_order == SortOrder.desc else column.asc()


# add-invitation-lifecycle-actions/design.md Decision 1: statuses eligible
# for reschedule (before check-in) vs. the "active visit" statuses extend
# and badge issuance operate on.
_RESCHEDULABLE_STATUSES = ("submitted", "approved")
_ACTIVE_STATUSES = ("approved", "checked_in")


class InvitationRepository(TenantScopedRepository[Invitation]):
    model = Invitation

    def _with_children(self) -> Select[tuple[Invitation]]:
        """Every read path below eventually serializes `visitors`/`vehicles`
        (`InvitationTrackingOut`), so both are eager-loaded here rather than
        left to the `lazy="raise"` relationships on `Invitation` to blow up
        at response-serialization time (query-performance.md §1).
        """
        return select(Invitation).options(
            selectinload(Invitation.visitors), selectinload(Invitation.vehicles)
        )

    async def get_with_children(self, id_: uuid.UUID) -> Invitation | None:
        stmt = self._with_children().where(Invitation.id == id_, Invitation.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def approve_if_submitted(self, id_: uuid.UUID) -> Invitation | None:
        """Atomic conditional transition: the `UPDATE` only affects a row
        that is still `submitted`, so two concurrent approval requests for
        the same invitation can't both transition it and both dispatch an
        approval notification — a plain read-then-write has no such
        guarantee (see codebase-review-and-e2e-scenario-test/design.md).
        Returns the updated row if this call performed the transition,
        `None` if the invitation was already approved (or lost the race to
        a concurrent call) — the caller treats `None` as "not currently
        submitted", the same 409 the sequential already-approved case
        already raises.
        """
        stmt = (
            update(Invitation)
            .where(Invitation.id == id_, Invitation.status == "submitted")
            .values(status="approved", approved_at=datetime.now(UTC))
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def deny_if_submitted(self, id_: uuid.UUID, *, reason: str) -> Invitation | None:
        """Atomic conditional transition, same shape as `approve_if_submitted`
        — see spec.md "A Submitted Invitation Can Be Denied With a Reason".
        """
        stmt = (
            update(Invitation)
            .where(Invitation.id == id_, Invitation.status == "submitted")
            .values(status="denied", denial_reason=reason, denied_at=datetime.now(UTC))
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def check_in_if_eligible(
        self, id_: uuid.UUID, *, user_id: uuid.UUID
    ) -> Invitation | None:
        """Only transitions a row that is both `approved` and not
        watchlist-flagged (spec.md "A Watchlist-Flagged Invitation Blocks
        Check-In Until Overridden") — both conditions are checked in the
        same atomic `UPDATE` so a concurrent override/check-in pair can't
        race past a read-then-write gap the way `approve_if_submitted`'s
        docstring already explains for the approve case.
        """
        stmt = (
            update(Invitation)
            .where(
                Invitation.id == id_,
                Invitation.status == "approved",
                Invitation.watchlist_flagged.is_(False),
            )
            .values(
                status="checked_in",
                checked_in_at=datetime.now(UTC),
                checked_in_by_user_id=user_id,
            )
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def check_out_if_checked_in(
        self, id_: uuid.UUID, *, user_id: uuid.UUID
    ) -> Invitation | None:
        stmt = (
            update(Invitation)
            .where(Invitation.id == id_, Invitation.status == "checked_in")
            .values(
                status="checked_out",
                checked_out_at=datetime.now(UTC),
                checked_out_by_user_id=user_id,
            )
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def reschedule_if_eligible(
        self, id_: uuid.UUID, *, preferred_visit_date: Any, preferred_visit_time: Any
    ) -> Invitation | None:
        stmt = (
            update(Invitation)
            .where(Invitation.id == id_, Invitation.status.in_(_RESCHEDULABLE_STATUSES))
            .values(
                preferred_visit_date=preferred_visit_date,
                preferred_visit_time=preferred_visit_time,
            )
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def extend_if_eligible(
        self, id_: uuid.UUID, *, new_expires_at: datetime
    ) -> Invitation | None:
        """The new-expiry-must-be-later check is folded into the `WHERE`
        clause too (`Invitation.expires_at < new_expires_at`), not just
        validated by the caller — so a concurrent extend to a later value
        can't be silently clobbered by a stale, earlier one that started
        first but committed second.
        """
        stmt = (
            update(Invitation)
            .where(
                Invitation.id == id_,
                Invitation.status.in_(_ACTIVE_STATUSES),
                Invitation.expires_at < new_expires_at,
            )
            .values(expires_at=new_expires_at)
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def issue_badge_if_eligible(
        self, id_: uuid.UUID, *, badge_number: str, badge_storage_key: str
    ) -> Invitation | None:
        stmt = (
            update(Invitation)
            .where(
                Invitation.id == id_,
                Invitation.status.in_(_ACTIVE_STATUSES),
                Invitation.badge_number.is_(None),
            )
            .values(
                badge_number=badge_number,
                badge_storage_key=badge_storage_key,
                badge_issued_at=datetime.now(UTC),
            )
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def reprint_badge_if_issued(
        self, id_: uuid.UUID, *, badge_storage_key: str
    ) -> Invitation | None:
        stmt = (
            update(Invitation)
            .where(Invitation.id == id_, Invitation.badge_number.is_not(None))
            .values(
                badge_storage_key=badge_storage_key,
                badge_reprint_count=Invitation.badge_reprint_count + 1,
            )
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def override_watchlist_if_flagged(
        self, id_: uuid.UUID, *, user_id: uuid.UUID, reason: str
    ) -> Invitation | None:
        stmt = (
            update(Invitation)
            .where(Invitation.id == id_, Invitation.watchlist_flagged.is_(True))
            .values(
                watchlist_flagged=False,
                watchlist_override_at=datetime.now(UTC),
                watchlist_override_by_user_id=user_id,
                watchlist_override_reason=reason,
            )
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_badge_number(self, badge_number: str) -> Invitation | None:
        """Backs `_generate_unique_badge_number`'s retry-against-uniqueness
        loop (design.md Decision 4) — same shape as tracking-id generation.
        """
        stmt = select(Invitation).where(Invitation.badge_number == badge_number)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_tracking_id(self, tracking_id: str) -> Invitation | None:
        stmt = self._with_children().where(
            Invitation.tracking_id == tracking_id, Invitation.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_primary_contact_email(self, email: str) -> list[Invitation]:
        """Backs the email-based tracking lookup (spec.md "Public Lookup by
        Email Is Rate-Limited and Minimally Revealing") — no eager-load of
        children here, since that endpoint only ever returns tracking id +
        status, never visitor/vehicle detail.
        """
        stmt = select(Invitation).where(
            Invitation.primary_contact_email == email, Invitation.deleted_at.is_(None)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_page(
        self,
        *,
        branch_scope: BranchScope,
        status: str | None,
        registration_type: str | None,
        source: str | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[Invitation], int]:
        """Backs `GET /invitations` (design.md Decision 2) — deliberately no
        `selectinload` of visitors/vehicles here (unlike `_with_children`
        above), since `InvitationListItemOut` doesn't serialize either.
        """
        column = {"submitted_at": Invitation.submitted_at, "created_at": Invitation.created_at}[
            sort_by
        ]
        branch_filter = _branch_filter(branch_scope)
        filters: list[Any] = [f for f in [branch_filter] if f is not None]
        if status is not None:
            filters.append(Invitation.status == status)
        if registration_type is not None:
            filters.append(Invitation.registration_type == registration_type)
        if source is not None:
            filters.append(Invitation.source == source)
        return await super().paginate(
            page=page,
            page_size=page_size,
            order_by=_order_clause(column, sort_order),
            filters=filters,
        )

    def add_visitors(self, visitors: list[InvitationVisitor]) -> None:
        """One `session.add_all` for every co-visitor row from a single
        submission — never a per-row `session.add()`/query loop
        (query-performance.md §3).
        """
        self.session.add_all(visitors)

    def add_vehicles(self, vehicles: list[InvitationVehicle]) -> None:
        self.session.add_all(vehicles)
