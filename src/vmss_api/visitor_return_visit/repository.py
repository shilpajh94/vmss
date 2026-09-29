from sqlalchemy import ColumnElement, or_, select

from vmss_api.core.database import TenantScopedRepository
from vmss_api.invitations.models import Invitation


class VisitorReturnVisitRepository(TenantScopedRepository[Invitation]):
    """Read-only lookups against `Invitation`, keyed by contact match rather
    than by id. Queries `invitations`' table directly rather than through
    `InvitationRepository` — see
    `openspec/changes/visitor-return-visit-login/design.md` Decision 1.
    """

    model = Invitation

    @staticmethod
    def _contact_filter(identifier: str) -> ColumnElement[bool]:
        return or_(
            Invitation.primary_contact_email == identifier,
            Invitation.primary_contact_phone == identifier,
        )

    async def get_most_recent(self, identifier: str) -> Invitation | None:
        stmt = (
            select(Invitation)
            .where(self._contact_filter(identifier), Invitation.deleted_at.is_(None))
            .order_by(Invitation.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_history(
        self, identifier: str, *, page: int, page_size: int
    ) -> tuple[list[Invitation], int]:
        """Newest-first, paginated (`api-conventions.md` §1) via the shared
        `TenantScopedRepository.paginate` primitive (`query-performance.md`
        §1 — one count query, one page query, no per-row loop).
        """
        return await self.paginate(
            page=page,
            page_size=page_size,
            order_by=Invitation.created_at.desc(),
            filters=(self._contact_filter(identifier),),
        )
