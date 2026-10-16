"""Seeds the QA fixtures every QA suite shares (API regression runner,
VMMS_WEB browser e2e, Locust load test) into the local default tenant —
openspec/changes/full-stack-qa-and-load-testing, spec "Idempotent shared QA
fixtures".

Upserts by natural key (user email, branch code, building code, category
code, (category, step) for workflow rules), so re-running changes nothing.
Refuses any tenant other than the default one: local QA data lives only in
`tenant_default`, and a second tenant is never created for it.

Prerequisite: `scripts/seed_dev_data.py` (default tenant, MAIN branch,
role catalog, admin@example.com).

Usage: ddev exec uv run python scripts/qa_regression/seed_qa_fixtures.py \
    [--tenant-slug default]
"""

import argparse
import asyncio
import sys
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth import service as auth_service
from vmss_api.auth.models import Role, User, UserBranchRole
from vmss_api.core.config import settings
from vmss_api.core.database import AsyncSessionLocal, engine, tenant_session_scope
from vmss_api.core.security import hash_password
from vmss_api.org_structure.models import Branch, Building
from vmss_api.platform.models import SuperAdmin
from vmss_api.tenant.repository import TenantRepository
from vmss_api.visitors.models import ApprovalWorkflowRule, VisitorCategory

# Staff password logins are rejected ("must sign in via SSO"); QA staff get
# minted tokens instead (mint_tokens.py). The hash only exists because the
# column is NOT NULL.
QA_PASSWORD = "qa-not-for-login-1"

# The platform (superadmin) login does take a password, unlike tenant staff.
QA_SUPERADMIN_EMAIL = "qa.super@example.com"
QA_SUPERADMIN_PASSWORD = "qa-super-12345"

MAIN_BRANCH_CODE = settings.registration_default_branch_code
QA_B_BRANCH_CODE = "QA-B"
# Form-builder write tests run against this branch, never MAIN's live form.
QA_FORM_BUILDER_BRANCH_CODE = "QAFB"


@dataclass(frozen=True)
class QaUser:
    email: str
    full_name: str
    role: str | None
    branch_code: str | None


QA_USERS = (
    QaUser("qa.reception@example.com", "QA Reception", "reception", MAIN_BRANCH_CODE),
    QaUser("qa.security@example.com", "QA Security", "security", MAIN_BRANCH_CODE),
    QaUser("qa.host@example.com", "QA Host", "host", MAIN_BRANCH_CODE),
    QaUser("qa.approver@example.com", "QA Approver", "host", MAIN_BRANCH_CODE),
    QaUser("qa.norole@example.com", "QA No Role", None, None),
    QaUser("qa.branchb@example.com", "QA Branch B Reception", "reception", QA_B_BRANCH_CODE),
)

# (code, name, ordered approver roles). QA_SINGLE has no extra rules: its one
# step is the step-0 ownership step every invitation gets.
QA_CATEGORIES = (
    ("QA_SINGLE", "QA Single Step", ()),
    ("QA_MULTI", "QA Multi Step", ("reception", "host")),
)


async def _ensure_superadmin(db: AsyncSession) -> None:
    stmt = select(SuperAdmin).where(SuperAdmin.email == QA_SUPERADMIN_EMAIL)
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        db.add(
            SuperAdmin(
                id=uuid.uuid4(),
                email=QA_SUPERADMIN_EMAIL,
                hashed_password=hash_password(QA_SUPERADMIN_PASSWORD),
                full_name="QA Superadmin",
            )
        )
        await db.commit()
        print(f"  + superadmin {QA_SUPERADMIN_EMAIL}")


async def _ensure_branch(tenant_db: AsyncSession, code: str, name: str) -> Branch:
    stmt = select(Branch).where(Branch.code == code, Branch.deleted_at.is_(None))
    branch = (await tenant_db.execute(stmt)).scalar_one_or_none()
    if branch is None:
        branch = Branch(id=uuid.uuid4(), name=name, code=code)
        tenant_db.add(branch)
        await tenant_db.flush()
        print(f"  + branch {code}")
    return branch


async def _ensure_building(tenant_db: AsyncSession, branch: Branch, code: str, name: str) -> None:
    stmt = select(Building).where(Building.branch_id == branch.id, Building.deleted_at.is_(None))
    if (await tenant_db.execute(stmt)).scalars().first() is None:
        tenant_db.add(Building(id=uuid.uuid4(), branch_id=branch.id, name=name, code=code))
        await tenant_db.flush()
        print(f"  + building {code} on {branch.code}")


async def _ensure_user(
    tenant_db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    qa_user: QaUser,
    roles: dict[str, Role],
    branches: dict[str, Branch],
) -> None:
    user = (
        await tenant_db.execute(select(User).where(User.email == qa_user.email))
    ).scalar_one_or_none()
    if user is None:
        user = await auth_service.create_user(
            tenant_db,
            tenant_id=tenant_id,
            email=qa_user.email,
            hashed_password=hash_password(QA_PASSWORD),
            full_name=qa_user.full_name,
        )
        print(f"  + user {qa_user.email}")
    if qa_user.role is None:
        return
    role_id = roles[qa_user.role].id
    branch_id = branches[qa_user.branch_code].id if qa_user.branch_code else None
    stmt = select(UserBranchRole).where(
        UserBranchRole.user_id == user.id,
        UserBranchRole.role_id == role_id,
        UserBranchRole.branch_id == branch_id
        if branch_id is not None
        else UserBranchRole.branch_id.is_(None),
    )
    if (await tenant_db.execute(stmt)).scalar_one_or_none() is None:
        tenant_db.add(
            UserBranchRole(id=uuid.uuid4(), user_id=user.id, role_id=role_id, branch_id=branch_id)
        )
        await tenant_db.flush()
        print(f"  + {qa_user.email} -> {qa_user.role}@{qa_user.branch_code or 'company'}")


async def _ensure_category(
    tenant_db: AsyncSession,
    *,
    code: str,
    name: str,
    approver_roles: tuple[str, ...],
    roles: dict[str, Role],
) -> None:
    stmt = select(VisitorCategory).where(
        VisitorCategory.code == code, VisitorCategory.deleted_at.is_(None)
    )
    category = (await tenant_db.execute(stmt)).scalar_one_or_none()
    if category is None:
        category = VisitorCategory(id=uuid.uuid4(), code=code, name=name, form_schema=[])
        tenant_db.add(category)
        await tenant_db.flush()
        print(f"  + category {code}")
    for step_order, role_name in enumerate(approver_roles, start=1):
        rule_stmt = select(ApprovalWorkflowRule).where(
            ApprovalWorkflowRule.visitor_category_id == category.id,
            ApprovalWorkflowRule.step_order == step_order,
            ApprovalWorkflowRule.deleted_at.is_(None),
        )
        if (await tenant_db.execute(rule_stmt)).scalar_one_or_none() is None:
            tenant_db.add(
                ApprovalWorkflowRule(
                    id=uuid.uuid4(),
                    visitor_category_id=category.id,
                    step_order=step_order,
                    approver_role_id=roles[role_name].id,
                )
            )
            await tenant_db.flush()
            print(f"  + rule {code} step {step_order} -> {role_name}")


async def seed(tenant_slug: str) -> None:
    if tenant_slug != settings.default_tenant_slug:
        print(
            f"Refusing to seed tenant {tenant_slug!r}: QA fixtures live only in the default "
            f"tenant ({settings.default_tenant_slug!r}).",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if settings.environment.lower() == "production":
        print("Refusing to seed QA fixtures in production.", file=sys.stderr)
        raise SystemExit(2)

    try:
        async with AsyncSessionLocal() as db:
            tenant = await TenantRepository(db).get_by_slug(tenant_slug)
            await _ensure_superadmin(db)
        if tenant is None:
            print("No default tenant — run scripts/seed_dev_data.py first.", file=sys.stderr)
            raise SystemExit(1)

        print(f"Seeding QA fixtures into {tenant.schema_name}")
        async with tenant_session_scope(tenant.schema_name) as tenant_db:
            roles = {
                r.name: r
                for r in (await tenant_db.execute(select(Role).where(Role.deleted_at.is_(None))))
                .scalars()
                .all()
            }
            branches = {
                MAIN_BRANCH_CODE: await _ensure_branch(tenant_db, MAIN_BRANCH_CODE, "Main Branch"),
                QA_B_BRANCH_CODE: await _ensure_branch(tenant_db, QA_B_BRANCH_CODE, "QA Branch B"),
                QA_FORM_BUILDER_BRANCH_CODE: await _ensure_branch(
                    tenant_db, QA_FORM_BUILDER_BRANCH_CODE, "QA Form Builder Branch"
                ),
            }
            await _ensure_building(tenant_db, branches[MAIN_BRANCH_CODE], "QA-MAIN-T", "QA Tower")
            await _ensure_building(tenant_db, branches[QA_B_BRANCH_CODE], "QAB-T", "QA B Tower")
            for qa_user in QA_USERS:
                await _ensure_user(
                    tenant_db, tenant_id=tenant.id, qa_user=qa_user, roles=roles, branches=branches
                )
            for code, name, approver_roles in QA_CATEGORIES:
                await _ensure_category(
                    tenant_db, code=code, name=name, approver_roles=approver_roles, roles=roles
                )
            await tenant_db.commit()
        print("QA fixtures up to date.")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-slug", default=settings.default_tenant_slug)
    args = parser.parse_args()
    asyncio.run(seed(args.tenant_slug))


if __name__ == "__main__":
    main()
