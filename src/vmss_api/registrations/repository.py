from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.registrations.models import RegistrationDeviceKey


class RegistrationDeviceKeyRepository:
    """Not a `TenantScopedRepository` — `RegistrationDeviceKey` is a
    global-schema registry table, queried through a plain `get_db` session,
    the same posture `TenantRepository` takes for `Tenant` (there is no
    tenant schema to bind yet; resolving one is the point of this lookup).
    See database-architecture.md §2.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self) -> list[RegistrationDeviceKey]:
        """Every hash comparison is done in Python (`verify_password`), not
        as a `WHERE key_hash = ...` — Argon2 hashes are salted, so the same
        raw key never produces the same hash twice. The number of active
        device keys is expected to stay small (one per branch), so scanning
        them all per request is cheap.
        """
        stmt = select(RegistrationDeviceKey).where(RegistrationDeviceKey.is_active.is_(True))
        return list((await self.session.execute(stmt)).scalars().all())
