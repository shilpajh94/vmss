import uuid

from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload

from vmss_api.core.database import TenantScopedRepository
from vmss_api.invitations.models import Invitation, InvitationVehicle, InvitationVisitor


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

    def add_visitors(self, visitors: list[InvitationVisitor]) -> None:
        """One `session.add_all` for every co-visitor row from a single
        submission — never a per-row `session.add()`/query loop
        (query-performance.md §3).
        """
        self.session.add_all(visitors)

    def add_vehicles(self, vehicles: list[InvitationVehicle]) -> None:
        self.session.add_all(vehicles)
