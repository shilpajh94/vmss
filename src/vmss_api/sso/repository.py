from collections.abc import Sequence

from sqlalchemy import select

from vmss_api.core.database import TenantScopedRepository
from vmss_api.sso.models import SsoProvider, SsoRoleMapping


class SsoProviderRepository(TenantScopedRepository[SsoProvider]):
    model = SsoProvider

    async def get_enabled(self) -> SsoProvider | None:
        """Today's single-provider-per-tenant posture (design.md's
        Non-Goals) means "the enabled one" is unambiguous — this is the
        lookup both the login-initiate and the config-read/test endpoints
        use.
        """
        stmt = select(SsoProvider).where(
            SsoProvider.is_enabled.is_(True), SsoProvider.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_any(self) -> SsoProvider | None:
        """The tenant's provider config regardless of `is_enabled` — used by
        `GET/PUT /auth/sso/config`, which must show a disabled config back
        to the Admin who's about to re-enable it.
        """
        stmt = select(SsoProvider).where(SsoProvider.deleted_at.is_(None)).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()


class SsoRoleMappingRepository(TenantScopedRepository[SsoRoleMapping]):
    model = SsoRoleMapping

    async def get_by_group_claim_value(self, value: str) -> SsoRoleMapping | None:
        stmt = select(SsoRoleMapping).where(
            SsoRoleMapping.idp_group_claim_value == value, SsoRoleMapping.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_first_match(self, group_claim_values: Sequence[str]) -> SsoRoleMapping | None:
        """One `WHERE idp_group_claim_value IN (...)` for the whole set of
        groups a token carries, instead of looping one lookup per group —
        query-performance.md §2.
        """
        if not group_claim_values:
            return None
        stmt = select(SsoRoleMapping).where(
            SsoRoleMapping.idp_group_claim_value.in_(group_claim_values),
            SsoRoleMapping.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def list_all(self) -> list[SsoRoleMapping]:
        return await self.list(limit=1000)

    async def delete(self, mapping: SsoRoleMapping) -> None:
        """Hard-deleted, not soft-deleted — same disposable-config posture
        as `UserBranchRole`: the mapping itself carries no audit/business
        value once removed, only the fact that a role was granted via it
        (recorded in `AuditLog` at grant time) does.
        """
        await self.session.delete(mapping)
