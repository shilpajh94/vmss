import uuid

from sqlalchemy import select

from vmss_api.core.database import TenantScopedRepository
from vmss_api.visit_info.models import VisitDuration, VisitPurpose


class VisitPurposeRepository(TenantScopedRepository[VisitPurpose]):
    model = VisitPurpose

    async def list_active(self) -> list[VisitPurpose]:
        stmt = (
            select(VisitPurpose)
            .where(VisitPurpose.is_active.is_(True), VisitPurpose.deleted_at.is_(None))
            .order_by(VisitPurpose.sort_order.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_active(self, id_: uuid.UUID) -> VisitPurpose | None:
        """Used to validate `purposeId` on invitation/walk-in creation — an
        id must resolve to an *active* row, not merely a non-deleted one
        (spec.md "Unknown or cross-tenant id is rejected").
        """
        stmt = select(VisitPurpose).where(
            VisitPurpose.id == id_,
            VisitPurpose.is_active.is_(True),
            VisitPurpose.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class VisitDurationRepository(TenantScopedRepository[VisitDuration]):
    model = VisitDuration

    async def list_active(self) -> list[VisitDuration]:
        stmt = (
            select(VisitDuration)
            .where(VisitDuration.is_active.is_(True), VisitDuration.deleted_at.is_(None))
            .order_by(VisitDuration.sort_order.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_active(self, id_: uuid.UUID) -> VisitDuration | None:
        """Same posture as `VisitPurposeRepository.get_active`."""
        stmt = select(VisitDuration).where(
            VisitDuration.id == id_,
            VisitDuration.is_active.is_(True),
            VisitDuration.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
