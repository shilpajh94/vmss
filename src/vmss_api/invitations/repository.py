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
