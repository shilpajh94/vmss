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
- `Invitation.tracking_id = Use(...)` — polyfactory's default `String(20)`
  generator picks a *uniform random length between 0 and 20*, so roughly
  1 in 20 builds gets a genuinely empty string. That's silently harmless
  for the many tests that only ever compare `tracking_id` for equality,
  but `checkin-approval-workflow-improvements` made it load-bearing:
  the canonical check-in endpoint is now keyed by `tracking_id` in the URL
  path (`PATCH /api/v2/invitations/{trackingId}/check-in`), and an empty
  path segment doesn't match that route at all — a 404 in place of the
  test's actual expected outcome, intermittently, only for factory-built
  invitations. `Use(...)` pins it to a well-formed, non-empty value
  instead, matching the shape (`INV-XXXXXXXX`) real invitation creation
  generates.
"""

from secrets import token_hex
from typing import Any

from polyfactory import Use
from polyfactory.factories.sqlalchemy_factory import SQLAlchemyFactory

from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.audit_trail.models import AuditReportJob
from vmss_api.auth.models import AuditLog, Permission, Role, User, UserBranchRole
from vmss_api.invitations.models import Invitation, InvitationVehicle, InvitationVisitor
from vmss_api.notifications.models import DeviceToken
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
from vmss_api.sso.models import SsoProvider, SsoRoleMapping
from vmss_api.tenant.models import Tenant
from vmss_api.visit_info.models import VisitDuration, VisitPurpose
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
    # Same footgun as the other optional String columns above: polyfactory
    # generates a random non-None string for a plain `String | None` column
    # by default, and `avatar_url` (add-avatar-upload-and-verify-image-
    # storage) is now actually surfaced in API responses and resolved as a
    # storage key — an un-pinned random value there isn't just noise, it
    # gets treated as a real (bogus) key and turned into a broken URL.
    avatar_url = None


class UserBranchRoleFactory(SQLAlchemyFactory[UserBranchRole]):
    __model__ = UserBranchRole


class DeviceTokenFactory(SQLAlchemyFactory[DeviceToken]):
    __model__ = DeviceToken


class AuditLogFactory(SQLAlchemyFactory[AuditLog]):
    __model__ = AuditLog


class AuditReportJobFactory(SQLAlchemyFactory[AuditReportJob]):
    __model__ = AuditReportJob
    status = "pending"
    csv_storage_key = None
    pdf_storage_key = None
    error_message = None
    completed_at = None
    deleted_at = None


class CompanyFactory(SQLAlchemyFactory[Company]):
    __model__ = Company
    is_active = True
    deleted_at = None
    # Same rationale as `BranchFactory.contact_person_user_id = None` below:
    # a random UUID here would violate the `roles.id` FK unless a real role
    # happens to exist with that id — and unset is the common case anyway
    # (falls back to the tenant's `reception` role; role-based-invitation-workflow).
    default_host_role_id = None


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
    # The router maps this plain string column back through `ContactMethod`
    # when serializing detail/tracking responses — same rationale as
    # `_build_invitation`'s `registration_type`/`source` defaults in
    # `invitations/tests.py`, applied at the factory level since every
    # caller of this factory needs a valid value, not just that helper.
    primary_contact_preferred_contact_method = "email"
    # See module docstring — polyfactory's default String(20) generator can
    # produce an empty string, which broke every test keying off tracking_id
    # in a URL path.
    tracking_id = Use(lambda: f"INV-{token_hex(4).upper()}")
    approved_at = None
    carried_items: list[str] = []
    consents: dict[str, bool] = {}
    # Same shape rationale as `carried_items`/`consents` above — polyfactory
    # infers a JSONB column's random value from the column type alone, not
    # the model's more specific `dict[str, list[dict[str, Any]]]` Python
    # hint, and produces a random scalar-valued dict that fails
    # `InvitationDetailOut`/etc.'s stricter Pydantic type.
    group_field_values: dict[str, list[dict[str, Any]]] = {}
    # restructure-walkin-payload-by-field-id: these are now read back keyed
    # by field id (`router.py::_dict_to_custom_fields`/`_dict_to_consents`
    # parse every key as a UUID) — a polyfactory-generated random string key
    # would fail that parse for every test that doesn't actually exercise
    # custom-field content, same rationale as `group_field_values` above.
    custom_field_values: dict[str, Any] = {}
    primary_contact_custom_field_values: dict[str, Any] = {}
    visitors: list[InvitationVisitor] = []
    vehicles: list[InvitationVehicle] = []
    # Same FK-safety rationale as `BranchFactory.contact_person_user_id`:
    # these are the visit-info-lookup-api optional catalog FKs, all
    # nullable — a random polyfactory-generated UUID here would violate
    # each one's constraint unless a real row happens to exist with that id.
    purpose_id = None
    host_id = None
    duration_id = None
    department_id = None
    # Same FK-safety rationale for the explicit building override
    # (`d4e9a2b7c1f6_invitation_building_id`).
    building_id = None
    # add-invitation-point-of-contact: same FK-safety rationale.
    poc_user_id = None
    poc_role_id = None
    poc_name = None
    # Same FK-safety rationale — the invitation-multi-step-approval category
    # tag, nullable at the DB level for pre-existing rows.
    visitor_category_id = None
    # add-invitation-lifecycle-actions: same FK-safety rationale for the new
    # lifecycle actor columns, plus a representative "nothing has happened
    # yet" default for the rest — a fresh `submitted` row has no denial/
    # check-in/check-out/badge/watchlist-override state.
    denial_reason = None
    denied_at = None
    checked_in_at = None
    checked_in_by_user_id = None
    checked_out_at = None
    checked_out_by_user_id = None
    badge_number = None
    badge_storage_key = None
    badge_issued_at = None
    badge_reprint_count = 0
    watchlist_flagged = False
    watchlist_override_at = None
    watchlist_override_reason = None
    watchlist_override_by_user_id = None
    # add-invitation-approval-revert: same FK-safety / "nothing has happened
    # yet" rationale — a fresh row has never had its approval reverted.
    approval_reverted_at = None
    approval_reverted_by_user_id = None
    approval_revert_reason = None
    # add-qr-checkin-security: a fresh `submitted` row has no QR scan history
    # yet, same "nothing has happened yet" reasoning as the check-in/check-out
    # fields above — kept parallel to (not derived from) `status`.
    check_in_status = "unused"
    # checkin-approval-workflow-improvements: nullable, optional — a
    # representative row has no photo captured, same "nothing has happened
    # yet" default as denial_reason/badge_number/etc. above.
    primary_contact_photo_storage_key = None


class InvitationApprovalStepFactory(SQLAlchemyFactory[InvitationApprovalStep]):
    __model__ = InvitationApprovalStep
    deleted_at = None
    status = "pending"
    # Defaults to unset so every existing role-identified step build (which
    # always passes `approver_role_id=...` explicitly) doesn't also get a
    # polyfactory-generated random `approver_user_id`, which would violate
    # the `ck_invitation_approval_steps_approver_xor` CHECK constraint
    # (add-approval-step-id-and-host-routing) requiring exactly one of the
    # two to be set. A host-identified step build overrides this explicitly.
    approver_user_id = None
    acted_by_user_id = None
    acted_at = None
    escalation_minutes = None
    auto_approve_minutes = None
    escalates_at = None
    auto_approves_at = None
    # Same FK-violation rationale as `approver_user_id` above: unset unless a
    # test explicitly builds a delegated step.
    delegated_to_user_id = None
    delegated_by_user_id = None
    delegated_at = None


class InvitationVisitorFactory(SQLAlchemyFactory[InvitationVisitor]):
    __model__ = InvitationVisitor
    deleted_at = None
    # checkin-approval-workflow-improvements: nullable, optional — see
    # InvitationFactory.primary_contact_photo_storage_key above.
    photo_storage_key = None
    # restructure-walkin-payload-by-field-id: see
    # InvitationFactory.custom_field_values above.
    custom_field_values: dict[str, Any] = {}


class InvitationVehicleFactory(SQLAlchemyFactory[InvitationVehicle]):
    __model__ = InvitationVehicle
    deleted_at = None
    # restructure-walkin-payload-by-field-id: see
    # InvitationFactory.custom_field_values above.
    custom_field_values: dict[str, Any] = {}


class RegistrationDeviceKeyFactory(SQLAlchemyFactory[RegistrationDeviceKey]):
    __model__ = RegistrationDeviceKey
    is_active = True


class SsoProviderFactory(SQLAlchemyFactory[SsoProvider]):
    __model__ = SsoProvider
    is_enabled = True
    deleted_at = None


class SsoRoleMappingFactory(SQLAlchemyFactory[SsoRoleMapping]):
    __model__ = SsoRoleMapping
    deleted_at = None


class VisitPurposeFactory(SQLAlchemyFactory[VisitPurpose]):
    __model__ = VisitPurpose
    is_active = True
    deleted_at = None


class VisitDurationFactory(SQLAlchemyFactory[VisitDuration]):
    __model__ = VisitDuration
    is_active = True
    deleted_at = None
