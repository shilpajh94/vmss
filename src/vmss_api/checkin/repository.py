import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import and_, exists, func, literal_column, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.checkin.models import BadgePrint
from vmss_api.core.schemas import BranchScope
from vmss_api.core.tenancy import branch_filter
from vmss_api.invitations.models import Invitation
from vmss_api.invitations.repository import PHONE_DIGITS_SQL, phone_digits

_MIN_PHONE_DIGITS = 7


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class CheckinRepository:
    """Queries for the badge print flow. `session` is already bound to one
    tenant's schema (`database-architecture.md` §2). Reads `Invitation`
    read-only except for the single `id_verified_*` update; it owns
    `badge_prints`. Not a `TenantScopedRepository`: `badge_prints` is
    append-only, with no `deleted_at` for that base's soft-delete filter."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- visits -------------------------------------------------------------

    async def get_visit(self, visit_id: uuid.UUID) -> Invitation | None:
        stmt = select(Invitation).where(Invitation.id == visit_id, Invitation.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def _search_filters(self, q: str, branch_scope: BranchScope) -> list[Any]:
        filters: list[Any] = [Invitation.deleted_at.is_(None)]
        scope_filter = branch_filter(Invitation.branch_id, branch_scope)
        if scope_filter is not None:
            filters.append(scope_filter)
        matchers: list[Any] = [
            Invitation.primary_contact_full_name.ilike(f"%{_escape_like(q)}%", escape="\\"),
            # Exact on the two code fields — never LIKE (design Decision 3).
            Invitation.tracking_id == q,
            Invitation.checkin_code == q,
        ]
        digits = phone_digits(q)
        if len(digits) >= _MIN_PHONE_DIGITS:
            matchers.append(literal_column(PHONE_DIGITS_SQL) == digits)
        filters.append(or_(*matchers))
        return filters

    async def search_visits(
        self, q: str, branch_scope: BranchScope, *, limit: int, offset: int
    ) -> tuple[list[tuple[Invitation, bool]], int]:
        filters = self._search_filters(q, branch_scope)
        has_active = exists().where(
            and_(BadgePrint.visit_id == Invitation.id, BadgePrint.active.is_(True))
        )
        stmt = (
            select(Invitation, has_active.label("has_active_badge"))
            .where(*filters)
            .order_by(Invitation.created_at.desc(), Invitation.id)
            .limit(limit)
            .offset(offset)
        )
        rows = [(row[0], bool(row[1])) for row in (await self.session.execute(stmt)).all()]
        total = (
            await self.session.execute(select(func.count()).select_from(Invitation).where(*filters))
        ).scalar_one()
        return rows, total

    async def mark_id_verified(
        self, visit_id: uuid.UUID, *, user_id: uuid.UUID
    ) -> Invitation | None:
        """`COALESCE` keeps the original timestamp/verifier on a repeat call
        (the endpoint is idempotent)."""
        stmt = (
            update(Invitation)
            .where(Invitation.id == visit_id, Invitation.deleted_at.is_(None))
            .values(
                id_verified_at=func.coalesce(Invitation.id_verified_at, datetime.now(UTC)),
                id_verified_by_user_id=func.coalesce(Invitation.id_verified_by_user_id, user_id),
            )
            .returning(Invitation)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def set_photo_if_missing(
        self, visit_id: uuid.UUID, storage_key: str
    ) -> Invitation | None:
        """Atomic: only writes while no photo is stored, so two concurrent
        uploads can't overwrite each other. `None` means the visit is gone or
        already has a photo (the caller tells them apart)."""
        stmt = (
            update(Invitation)
            .where(
                Invitation.id == visit_id,
                Invitation.deleted_at.is_(None),
                Invitation.primary_contact_photo_storage_key.is_(None),
            )
            .values(primary_contact_photo_storage_key=storage_key)
            .returning(Invitation)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # --- badge_prints -------------------------------------------------------

    async def get_print(self, print_id: uuid.UUID) -> BadgePrint | None:
        return (
            await self.session.execute(select(BadgePrint).where(BadgePrint.id == print_id))
        ).scalar_one_or_none()

    async def get_print_by_jti(self, jti: str) -> BadgePrint | None:
        return (
            await self.session.execute(select(BadgePrint).where(BadgePrint.jti == jti))
        ).scalar_one_or_none()

    async def get_active_print(self, visit_id: uuid.UUID) -> BadgePrint | None:
        stmt = select(BadgePrint).where(
            BadgePrint.visit_id == visit_id, BadgePrint.active.is_(True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def has_any_print(self, visit_id: uuid.UUID) -> bool:
        stmt = select(exists().where(BadgePrint.visit_id == visit_id))
        return bool((await self.session.execute(stmt)).scalar_one())

    async def deactivate_active_for_visit(self, visit_id: uuid.UUID) -> None:
        """The only permitted mutation of an existing row: `active` -> false."""
        await self.session.execute(
            update(BadgePrint)
            .where(BadgePrint.visit_id == visit_id, BadgePrint.active.is_(True))
            .values(active=False)
        )

    async def deactivate_by_jti(self, jti: str) -> None:
        await self.session.execute(
            update(BadgePrint)
            .where(BadgePrint.jti == jti, BadgePrint.active.is_(True))
            .values(active=False)
        )

    async def insert_print(
        self,
        *,
        visit_id: uuid.UUID,
        printed_by_user_id: uuid.UUID,
        jti: str,
        day: date,
        reprint_reason: str | None,
    ) -> BadgePrint:
        row = BadgePrint(
            id=uuid.uuid4(),
            visit_id=visit_id,
            printed_by_user_id=printed_by_user_id,
            printed_at=datetime.now(UTC),
            jti=jti,
            day=day,
            active=True,
            reprint_reason=reprint_reason,
        )
        self.session.add(row)
        await self.session.flush()
        return row
