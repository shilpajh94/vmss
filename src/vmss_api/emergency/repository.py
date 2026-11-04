from datetime import datetime
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.access_control.models import Zone, ZoneAccessEvent
from vmss_api.core.schemas import BranchScope
from vmss_api.core.tenancy import branch_filter
from vmss_api.invitations.models import Invitation


class InsideRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _occupancy(self) -> Any:
        """Latest *allowed* event per (visit, zone); a denied scan neither puts a
        visit in a zone nor takes it out. One `DISTINCT ON`, no per-visit query."""
        return (
            select(
                ZoneAccessEvent.invitation_id,
                ZoneAccessEvent.zone_id,
                ZoneAccessEvent.direction,
                ZoneAccessEvent.occurred_at,
            )
            .where(ZoneAccessEvent.decision == "allowed")
            .distinct(ZoneAccessEvent.invitation_id, ZoneAccessEvent.zone_id)
            .order_by(
                ZoneAccessEvent.invitation_id,
                ZoneAccessEvent.zone_id,
                ZoneAccessEvent.occurred_at.desc(),
                ZoneAccessEvent.id.desc(),
            )
            .subquery("occupancy")
        )

    def _inside_filters(self, branch_scope: BranchScope) -> list[Any]:
        filters: list[Any] = [
            Invitation.deleted_at.is_(None),
            Invitation.check_in_status == "checked_in",
        ]
        scope = branch_filter(Invitation.branch_id, branch_scope)
        if scope is not None:
            filters.append(scope)
        return filters

    async def occupants_by_zone(
        self, branch_scope: BranchScope
    ) -> list[tuple[Zone, Invitation, datetime]]:
        occ = self._occupancy()
        stmt = (
            select(Zone, Invitation, occ.c.occurred_at)
            .select_from(occ)
            .join(Zone, Zone.id == occ.c.zone_id)
            .join(Invitation, Invitation.id == occ.c.invitation_id)
            .where(
                occ.c.direction == "entry",
                Zone.deleted_at.is_(None),
                *self._inside_filters(branch_scope),
            )
            .order_by(Zone.name, Zone.id, occ.c.occurred_at, Invitation.id)
        )
        return [(z, i, t) for z, i, t in (await self.session.execute(stmt)).all()]

    async def unzoned(self, branch_scope: BranchScope) -> list[Invitation]:
        """Checked in, but not currently inside any zone (never scanned in, or
        exited every zone) — reconciles this report with the dashboard `insideNow`."""
        occ = self._occupancy()
        in_a_zone = exists().where(occ.c.invitation_id == Invitation.id, occ.c.direction == "entry")
        stmt = (
            select(Invitation)
            .where(~in_a_zone, *self._inside_filters(branch_scope))
            .order_by(Invitation.checked_in_at, Invitation.id)
        )
        return list((await self.session.execute(stmt)).scalars().all())
