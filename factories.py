"""Test-data factories (testing-standards.md §1) — one `SQLAlchemyFactory`
per model that tests/fixtures construct directly. Building a row via
`XFactory.build(**overrides)` fills every column `conftest.py`/a test doesn't
explicitly care about with a valid value, so a new required column on a model
fails loudly here (once) instead of a dozen hand-built fixtures silently
producing rows that happen to still pass.

Lives at the repo root, next to `conftest.py` — `tests/` has no `__init__.py`
(see `fastapi-architecture.md` §1's single-import-path stance applied to test
code too), so a sibling of `conftest.py` is importable the same way
(`from factories import ...`) from every test module without needing one.

A few fields are pinned to a fixed value rather than left to polyfactory's
random generation, because "random" would be actively wrong here, not just
arbitrary:
- `is_active = True` — `SQLAlchemyFactory` fills non-nullable `bool` columns
  with a random `True`/`False`; a freshly built row defaulting to *inactive*
  half the time would make login/permission checks flake for reasons
  unrelated to whatever the test is actually checking.
- `deleted_at = None` — same issue for the soft-delete column: a random past
  timestamp here makes every repository query in `core/database.py`
  (`TenantScopedRepository`'s `deleted_at IS NULL` filter) silently exclude
  the row that was just built.
- `branch_roles = []` / `permissions = []` — these relationships are the
  crux of most RBAC test setups; every test that cares overrides them
  explicitly (`UserFactory.build(branch_roles=[...])`), so the factory
  default must be an empty list, not polyfactory recursively fabricating an
  unrelated nested row with dangling foreign keys.
"""

from polyfactory.factories.sqlalchemy_factory import SQLAlchemyFactory

from vmss_api.auth.models import Permission, Role, User, UserBranchRole
from vmss_api.invitations.models import Invitation, InvitationVehicle, InvitationVisitor
from vmss_api.org_structure.models import (
    Branch,
    Building,
    Company,
    Department,
    Floor,
    ReceptionDesk,
    SecurityGate,
)
from vmss_api.platform.models import SuperAdmin
from vmss_api.registrations.models import RegistrationDeviceKey
from vmss_api.tenant.models import Tenant
from vmss_api.visitors.models import ApprovalWorkflowRule, VisitorCategory


class TenantFactory(SQLAlchemyFactory[Tenant]):
    __model__ = Tenant
    is_active = True
    deleted_at = None


class SuperAdminFactory(SQLAlchemyFactory[SuperAdmin]):
    __model__ = SuperAdmin
    is_active = True
    deleted_at = None


class PermissionFactory(SQLAlchemyFactory[Permission]):
    __model__ = Permission
    deleted_at = None


class RoleFactory(SQLAlchemyFactory[Role]):
    __model__ = Role
    deleted_at = None
    permissions: list[Permission] = []


class UserFactory(SQLAlchemyFactory[User]):
    __model__ = User
    is_active = True
    deleted_at = None
    branch_roles: list[UserBranchRole] = []
    employee_code = None
    designation = None
    phone_number = None
    department_id = None


class UserBranchRoleFactory(SQLAlchemyFactory[UserBranchRole]):
    __model__ = UserBranchRole


class CompanyFactory(SQLAlchemyFactory[Company]):
    __model__ = Company
    is_active = True
    deleted_at = None


class BranchFactory(SQLAlchemyFactory[Branch]):
    __model__ = Branch
    is_active = True
    deleted_at = None
    # Same rationale as `UserFactory.department_id = None` below: a random
    # UUID here would violate the `users.id` FK unless a real user happens
    # to exist with that id.
    contact_person_user_id = None


class BuildingFactory(SQLAlchemyFactory[Building]):
    __model__ = Building
    is_active = True
    deleted_at = None


class FloorFactory(SQLAlchemyFactory[Floor]):
    __model__ = Floor
    is_active = True
    deleted_at = None


class DepartmentFactory(SQLAlchemyFactory[Department]):
    __model__ = Department
    is_active = True
    deleted_at = None
    # Same FK-safety rationale as `BranchFactory.contact_person_user_id`.
    head_of_department_user_id = None


class ReceptionDeskFactory(SQLAlchemyFactory[ReceptionDesk]):
    __model__ = ReceptionDesk
    status = "active"
    deleted_at = None
    # Same FK-safety rationale as `BranchFactory.contact_person_user_id`.
    assigned_receptionist_user_id = None


class SecurityGateFactory(SQLAlchemyFactory[SecurityGate]):
    __model__ = SecurityGate
    connectivity_status = "online"
    high_security = False
    deleted_at = None


class VisitorCategoryFactory(SQLAlchemyFactory[VisitorCategory]):
    __model__ = VisitorCategory
    is_active = True
    deleted_at = None
    form_schema: list[dict] = []


class ApprovalWorkflowRuleFactory(SQLAlchemyFactory[ApprovalWorkflowRule]):
    __model__ = ApprovalWorkflowRule
    is_active = True
    deleted_at = None
    escalation_minutes = None
    auto_approve_minutes = None


class InvitationFactory(SQLAlchemyFactory[Invitation]):
    """Creation now populates every field in one call (no more `pending`
    shell state — `merge-invitation-registration-into-creation/design.md`
    Decision 2), so a representative row has `status="submitted"` with
    every other field present; only `deleted_at`/children default to empty.
    """

    __model__ = Invitation
    deleted_at = None
    status = "submitted"
    carried_items: list[str] = []
    visitors: list[InvitationVisitor] = []
    vehicles: list[InvitationVehicle] = []


class InvitationVisitorFactory(SQLAlchemyFactory[InvitationVisitor]):
    __model__ = InvitationVisitor
    deleted_at = None


class InvitationVehicleFactory(SQLAlchemyFactory[InvitationVehicle]):
    __model__ = InvitationVehicle
    deleted_at = None


class RegistrationDeviceKeyFactory(SQLAlchemyFactory[RegistrationDeviceKey]):
    __model__ = RegistrationDeviceKey
    is_active = True
