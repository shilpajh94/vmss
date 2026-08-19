"""Provisions a walk-in-registration device credential for one branch
(API-13) — issues the raw `X-Device-Key` value a kiosk/app instance
presents to `POST /api/v1/registrations/walk-in`, storing only its Argon2
hash. The raw key is printed exactly once here; there is no way to recover
it afterward, only to issue a new one and deactivate the old.

No management endpoint exists for this yet (design.md Decision 3's
"Provisioning" note) — this script is the only way to issue one today.

Usage: ddev exec uv run python scripts/provision_registration_device.py \
    --tenant-slug acme --branch-id <uuid> --label "Main Branch kiosk"
"""

import argparse
import asyncio
import secrets
import uuid

from vmss_api.core.database import AsyncSessionLocal
from vmss_api.core.security import hash_password
from vmss_api.registrations.models import RegistrationDeviceKey
from vmss_api.tenant.repository import TenantRepository


async def _run(tenant_slug: str, branch_id: uuid.UUID, label: str) -> None:
    async with AsyncSessionLocal() as db:
        tenant = await TenantRepository(db).get_by_slug(tenant_slug)
        if tenant is None:
            raise SystemExit(f"No tenant with slug {tenant_slug!r}")

        raw_key = secrets.token_urlsafe(32)
        device_key = RegistrationDeviceKey(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            branch_id=branch_id,
            key_hash=hash_password(raw_key),
            label=label,
        )
        db.add(device_key)
        await db.commit()

    print(f"Provisioned device key {device_key.id} for tenant {tenant_slug!r}, branch {branch_id}")
    print(f"X-Device-Key: {raw_key}")
    print("Store this value now — it cannot be recovered later.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-slug", required=True, help="e.g. 'acme'")
    parser.add_argument("--branch-id", required=True, type=uuid.UUID, help="Branch UUID")
    parser.add_argument("--label", required=True, help="e.g. 'Main Branch kiosk'")
    args = parser.parse_args()
    asyncio.run(_run(args.tenant_slug, args.branch_id, args.label))


if __name__ == "__main__":
    main()
