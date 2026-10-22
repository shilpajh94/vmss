"""Mints access tokens for every QA role and writes them to
`var/qa/tokens.json` (gitignored), for the API regression runner, the
VMMS_WEB browser e2e suite and the Locust load test.

Tenant staff can't password-login (they must use SSO), so tokens are minted
directly. Tokens carry a run-length TTL (default 6 h, capped at 6 h) and are
only ever minted against the local default tenant.

Output shape:
    {"tenantId": ..., "branches": {"MAIN": id, "QA-B": id, "QAFB": id},
     "categories": {"QA_SINGLE": id, "QA_MULTI": id},
     "users": {"admin": {"email", "userId", "token"}, "reception": {...}, ...},
     "superadmin": {"email", "token"}, "visitor": {"email", "token"}}

Usage: ddev exec uv run python scripts/qa_regression/mint_tokens.py [--hours 6]
"""

import argparse
import asyncio
import json
import sys
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.core.database import AsyncSessionLocal, engine, tenant_session_scope
from vmss_api.core.security import _create_token
from vmss_api.org_structure.models import Branch
from vmss_api.platform.models import SuperAdmin
from vmss_api.tenant.repository import TenantRepository
from vmss_api.visitors.models import VisitorCategory

MAX_HOURS = 6
OUT_PATH = Path(__file__).resolve().parents[2] / "var" / "qa" / "tokens.json"

# Runner-facing role key -> account email.
ROLE_ACCOUNTS = {
    "admin": "admin@example.com",
    "reception": "qa.reception@example.com",
    "security": "qa.security@example.com",
    "host": "qa.host@example.com",
    "approver": "qa.approver@example.com",
    "norole": "qa.norole@example.com",
    "branchb": "qa.branchb@example.com",
}
SUPERADMIN_EMAIL = "qa.super@example.com"
# A visitor who "passed" OTP, for the visitor-portal routes (the raw OTP code
# is only ever stored hashed, so a real verify can't be scripted).
VISITOR_EMAIL = "qa.visitor@example.com"


async def mint(hours: int) -> dict:
    ttl = timedelta(hours=min(hours, MAX_HOURS))
    try:
        async with AsyncSessionLocal() as db:
            tenant = await TenantRepository(db).get_by_slug(settings.default_tenant_slug)
            superadmin = (
                await db.execute(select(SuperAdmin).where(SuperAdmin.email == SUPERADMIN_EMAIL))
            ).scalar_one_or_none()
        if tenant is None:
            raise SystemExit("No default tenant — run scripts/seed_dev_data.py first.")

        async with tenant_session_scope(tenant.schema_name) as tenant_db:
            users = {
                u.email: u
                for u in (
                    await tenant_db.execute(
                        select(User).where(User.email.in_(ROLE_ACCOUNTS.values()))
                    )
                )
                .scalars()
                .all()
            }
            branches = {
                b.code: str(b.id)
                for b in (
                    await tenant_db.execute(
                        select(Branch).where(
                            Branch.code.in_(
                                [settings.registration_default_branch_code, "QA-B", "QAFB"]
                            ),
                            Branch.deleted_at.is_(None),
                        )
                    )
                )
                .scalars()
                .all()
            }
            categories = {
                c.code: str(c.id)
                for c in (
                    await tenant_db.execute(
                        select(VisitorCategory).where(
                            VisitorCategory.code.in_(["QA_SINGLE", "QA_MULTI"]),
                            VisitorCategory.deleted_at.is_(None),
                        )
                    )
                )
                .scalars()
                .all()
            }
    finally:
        await engine.dispose()

    missing = [email for email in ROLE_ACCOUNTS.values() if email not in users]
    if missing:
        raise SystemExit(
            f"Missing QA users {missing} — run scripts/qa_regression/seed_qa_fixtures.py first."
        )

    result: dict = {
        "tenantId": str(tenant.id),
        "branches": branches,
        "categories": categories,
        "users": {
            role: {
                "email": email,
                "userId": str(users[email].id),
                "token": _create_token(users[email].id, tenant.id, ttl, "access"),
            }
            for role, email in ROLE_ACCOUNTS.items()
        },
    }
    result["visitor"] = {
        "email": VISITOR_EMAIL,
        # Same claims as create_identity_verified_token, with the run's TTL
        # instead of its 15 minutes.
        "token": _create_token(
            VISITOR_EMAIL, tenant.id, ttl, "identity_verified", extra_claims={"channel": "email"}
        ),
    }
    if superadmin is not None:
        result["superadmin"] = {
            "email": SUPERADMIN_EMAIL,
            "token": _create_token(superadmin.id, None, ttl, "platform_access"),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=MAX_HOURS)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()

    tokens = asyncio.run(mint(args.hours))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(tokens, indent=2))
    args.out.chmod(0o600)
    print(f"Wrote tokens for {', '.join(tokens['users'])} to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
