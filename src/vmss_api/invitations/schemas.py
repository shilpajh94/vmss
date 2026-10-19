import uuid
from datetime import date, datetime, time
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import (
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from vmss_api.approvals.schemas import CurrentApprovalStepOut
from vmss_api.core.schemas import CamelModel
from vmss_api.devices.schemas import DeviceBriefOut

InvitationSortableField = Literal["submitted_at", "created_at"]
"""Whitelisted `sortBy` values for `GET /invitations` (api-conventions.md
§1) — mirrors `org_structure/schemas.py`'s `SortableField` pattern.
"""


def _blank_id_proof_type_to_none(value: Any) -> Any:
    """`idProofType` is optional: a client sending `""` or the string
    `"null"` means "not provided", not an (invalid) option value.
    """
    if isinstance(value, str) and value.strip().lower() in {"", "null"}:
        return None
    return value


class RegistrationType(StrEnum):
    individual = "individual"
    group = "group"


class InvitationStatus(StrEnum):
    """The closed set of values `Invitation.status` is ever written by
    application code — `models.py`'s state-machine writes (`create_invitation`,
    `approve_if_submitted`, `deny_if_submitted`, `check_in_if_eligible`/
    `check_in_by_qr_if_eligible`, `check_out_if_checked_in`/
    `check_out_by_qr_if_eligible`, `archive_expired_no_shows`, `service.py`'s
    `initial_status`). `pending` is the column's DB-level default but is
    never produced by any code path (see `models.py::Invitation`'s own
    docstring) — deliberately excluded so `GET /invitations?status=` can't
    be used to fish for a state that no row can actually be in.
    `api-conventions.md` §1's real-enum-filter rule, matching
    `RegistrationType`/`RegistrationSource` above.
    """

    submitted = "submitted"
    approved = "approved"
    denied = "denied"
    checked_in = "checked_in"
    checked_out = "checked_out"
    archived = "archived"


class RegistrationSource(StrEnum):
    """Which channel created the `Invitation` row — an employee's advance
    pre-registration (API-09) or a visitor's own walk-in registration
    (API-13, `registrations` capability). See
    add-walkin-visitor-registration/design.md Decision 1.
    """

    staff_pre_registration = "staff_pre_registration"
    visitor_walk_in = "visitor_walk_in"


class ContactMethod(StrEnum):
    email = "email"
    sms = "sms"


# --- Admin-authored answers, joined by field/group id — never by key -------
# (restructure-walkin-payload-by-field-id): a `FormField`/`FormFieldGroup`'s
# `key` is authored once and, as implemented, never renamed after creation —
# but `id` is the identifier this system actually guarantees stable, so the
# submission/response wire contract is built around it instead. See
# proposal.md's "Why" and design.md Decisions 1-2.


class CustomFieldValue(CamelModel):
    field_id: uuid.UUID
    field_name: str | None = Field(
        default=None, description="Admin-facing label of the field (response only)."
    )
    field_key: str | None = Field(
        default=None, description="Stable key of the field (response only)."
    )
    value: Any = None


class ConsentValue(CamelModel):
    field_id: uuid.UUID
    field_name: str | None = Field(
        default=None, description="Admin-facing label of the field (response only)."
    )
    field_key: str | None = Field(
        default=None, description="Stable key of the field (response only)."
    )
    accepted: bool


class FieldGroupSubmit(CamelModel):
    group_id: uuid.UUID
    instances: list[list[CustomFieldValue]] = Field(default_factory=list, max_length=50)


class FieldGroupValuesOut(CamelModel):
    """Response-side counterpart of `FieldGroupSubmit` — one repeatable
    group's submitted instances, each a list of `{fieldId, value}` pairs."""

    group_id: uuid.UUID
    group_name: str | None = Field(
        default=None, description="Admin-facing name of the group (response only)."
    )
    instances: list[list[CustomFieldValue]] = Field(default_factory=list)


def _custom_fields_to_dict(items: list[CustomFieldValue], *, scope: str) -> dict[str, Any]:
    """Converts the wire's `list[{fieldId, value}]` shape into the
    `{str(fieldId): value}` map every internal validation/persistence
    helper (`form_builder/validation.py`, `invitations/service.py`) works
    with — see design.md Decision 3.2. Rejects a duplicate `fieldId` within
    the same scope structurally, before any branch-configuration lookup.
    """
    result: dict[str, Any] = {}
    for item in items:
        key = str(item.field_id)
        if key in result:
            raise ValueError(f"Duplicate fieldId '{key}' in {scope}")
        result[key] = item.value
    return result


def _consents_to_dict(items: list[ConsentValue]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for item in items:
        key = str(item.field_id)
        if key in result:
            raise ValueError(f"Duplicate fieldId '{key}' in consents")
        result[key] = item.accepted
    return result


def _groups_to_dict(items: list[FieldGroupSubmit]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        key = str(item.group_id)
        if key in result:
            raise ValueError(f"Duplicate groupId '{key}' in groups")
        result[key] = [
            _custom_fields_to_dict(instance, scope=f"group '{key}' instance")
            for instance in item.instances
        ]
    return result


def _require_reachable_contact(email: str | None, phone: str | None) -> None:
    """Shared rule for every visitor entry (spec.md "Each Visitor Has at
    Least One Reachable Contact and an ID Proof"): at least one of
    email/phone must be present.
    """
    if not email and not phone:
        raise ValueError("At least one of email or phone is required")


def _require_contact_for_method(
    email: str | None, phone: str | None, method: "ContactMethod"
) -> None:
    """The primary contact additionally has a `preferredContactMethod`
    (`invitations/tasks.py::_dispatch` routes on it) — "at least one of
    email/phone" isn't enough on its own if the *chosen* channel's field is
    the one left empty (e.g. `preferredContactMethod: "sms"` with only an
    email on file), since dispatch would then have nothing to send to.
    """
    if method == ContactMethod.email and not email:
        raise ValueError("email is required when preferredContactMethod is 'email'")
    if method == ContactMethod.sms and not phone:
        raise ValueError("phone is required when preferredContactMethod is 'sms'")


# --- Shared nested request shapes, used by the single invitation-creation --
# call below (design.md Decision 1: these were API-10's `SelfRegistrationSubmit`
# fields, now folded into `InvitationCreate` directly). ------------------------


class VisitorSubmit(CamelModel):
    full_name: str = Field(max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    # Optional (form-builder): whether ID proof is captured at all is now
    # branch-configurable — see `invitations/service.py::create_invitation`'s
    # dynamic requiredness check against the effective form. Plain string,
    # not a fixed enum (make-id-proof-and-vehicle-type-configurable): a
    # valid value is whatever the calling branch's published Visitor Info
    # "ID Proof Type" field currently declares as an option — validated
    # dynamically in `invitations/service.py::create_invitation`, not by
    # this schema, mirroring `CarriedItemsSubmit.items` below.
    id_proof_type: str | None = Field(default=None, max_length=100)

    _normalize_id_proof_type = field_validator("id_proof_type", mode="before")(
        _blank_id_proof_type_to_none
    )
    # This visitor's own answers for any admin-authored Visitor Info field
    # (add-generic-custom-field-support), referenced by field id
    # (restructure-walkin-payload-by-field-id) — validated dynamically
    # against the effective form in
    # `invitations/service.py::create_invitation`, not by this schema.
    custom_fields: list[CustomFieldValue] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _check_contact(self) -> Self:
        _require_reachable_contact(self.email, self.phone)
        _custom_fields_to_dict(self.custom_fields, scope="a visitor's customFields")
        return self

    @property
    def custom_field_values(self) -> dict[str, Any]:
        """`{str(fieldId): value}` — see `_custom_fields_to_dict`."""
        return _custom_fields_to_dict(self.custom_fields, scope="a visitor's customFields")


class VisitDetailsSubmit(CamelModel):
    # Location of the visit. Preferred home for these ids; the top-level
    # `branchId`/`buildingId` on `InvitationCreate` remain accepted as a
    # fallback for older clients (see `InvitationCreate.effective_*`).
    branch_id: uuid.UUID | None = None
    building_id: uuid.UUID | None = None
    purpose_of_visit: str = Field(max_length=255)
    # Never client-supplied for routing purposes anymore
    # (role-based-invitation-workflow) — the invitation's host is resolved
    # exclusively by delegating its ownership step (see the `approvals`
    # capability), never by anything submitted here. Both fields are still
    # accepted, for backward compatibility with an un-updated client, but
    # silently ignored by the service layer rather than rejected.
    host_name_or_email: str | None = Field(default=None, max_length=255)
    preferred_visit_date: date
    preferred_visit_time: time
    # Unconditionally optional (make-expected-duration-optional) — unlike
    # `purpose_of_visit`/the date/time fields above, which stay hardcoded
    # required. Neither visitor-facing wizard collects this field any more,
    # so there's no dynamic branch-config required-check for it either
    # (see `create_invitation`'s note next to `id_proof_required`/
    # `photo_required`) — hardcoding it required here would reject every
    # submission unconditionally, since no client could ever supply it.
    expected_duration: str | None = Field(default=None, max_length=50)
    # Optional (allow-optional-department-at-creation) — a visitor or the
    # staff member creating an invitation on their behalf often doesn't know
    # the receiving organisation's internal department structure. Left
    # unset, it's filled in later via `PATCH /invitations/{id}/edit`.
    department_to_visit: str | None = Field(default=None, max_length=255)
    additional_notes: str | None = Field(default=None, max_length=2000)
    # Optional catalog ids (visit-info-lookup-api) — when supplied, the
    # service layer validates each against its catalog/`Department`/`User`
    # and overwrites the paired free-text field above with that row's
    # canonical display value before persisting. Omitted entirely, behavior
    # is unchanged: the free-text fields above are stored exactly as
    # submitted. See openspec/changes/visit-info-lookup-api/design.md.
    purpose_id: uuid.UUID | None = None
    host_id: uuid.UUID | None = None
    duration_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None


class CarriedItemsSubmit(CamelModel):
    # Plain strings, not a fixed enum (form-builder): a valid key is
    # whatever the calling branch's published Carried Items step currently
    # declares as an option — validated dynamically in
    # `invitations/service.py::create_invitation`, not by this schema.
    items: list[Annotated[str, Field(max_length=100)]] = Field(default_factory=list, max_length=50)
    item_description: str | None = Field(default=None, max_length=2000)


class VehicleSubmit(CamelModel):
    # Plain string, not a fixed enum (make-id-proof-and-vehicle-type-
    # configurable): a valid value is whatever the calling branch's
    # published Vehicle Info "Vehicle Type" field currently declares as an
    # option — validated dynamically in
    # `invitations/service.py::create_invitation`, not by this schema.
    vehicle_type: str = Field(max_length=50)
    license_plate: str = Field(max_length=50)
    make_model: str | None = Field(default=None, max_length=255)
    color: str | None = Field(default=None, max_length=50)
    # This vehicle's own answers for any admin-authored Vehicle Info field
    # beyond the locked license-plate field (add-generic-custom-field-
    # support), referenced by field id (restructure-walkin-payload-by-
    # field-id) — validated dynamically against the effective form in
    # `invitations/service.py::create_invitation`.
    custom_fields: list[CustomFieldValue] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _check_custom_fields(self) -> Self:
        _custom_fields_to_dict(self.custom_fields, scope="a vehicle's customFields")
        return self

    @property
    def custom_field_values(self) -> dict[str, Any]:
        return _custom_fields_to_dict(self.custom_fields, scope="a vehicle's customFields")


# --- API-09: employee creates a fully completed invitation in one call -----


class InvitationPrimaryContactCreate(CamelModel):
    full_name: str = Field(max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    preferred_contact_method: ContactMethod = ContactMethod.email
    # Optional (form-builder) — see `VisitorSubmit.id_proof_type`.
    id_proof_type: str | None = Field(default=None, max_length=100)

    _normalize_id_proof_type = field_validator("id_proof_type", mode="before")(
        _blank_id_proof_type_to_none
    )
    # Accepted but ignored: the primary contact's Visitor Info-step answers
    # are sourced from the invitation-level `customFields` array instead —
    # there's exactly one primary contact per invitation, so a flat
    # field-id-keyed map unambiguously recovers "the primary contact's
    # answers" without a separate nested array (see
    # `InvitationCreate.custom_field_values`/
    # `service.py::create_invitation`). This field is kept only so an
    # already-deployed client that still sends it doesn't get a hard
    # validation error.
    custom_fields: list[CustomFieldValue] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _check_contact(self) -> Self:
        _require_contact_for_method(self.email, self.phone, self.preferred_contact_method)
        _custom_fields_to_dict(self.custom_fields, scope="the primary contact's customFields")
        return self


class InvitationCreate(CamelModel):
    """Parsed from the multipart request's JSON `payload` part — see
    `router.py::create_invitation`. ID-proof file parts
    (`primaryContact.idProofFile`, `visitors[i].idProofFile`) travel
    alongside as separate multipart parts, matched to this schema's
    `visitors` list by index.
    """

    registration_type: RegistrationType
    branch_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Which branch this invitation belongs to. Falls back to the "
            "`X-Branch-ID` header when omitted here; one of the two is "
            "required."
        ),
    )
    building_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Optional building within the branch being visited; must belong "
            "to that branch. Shown back as `building` on the invitation detail."
        ),
    )
    visitor_category_id: uuid.UUID = Field(
        description=(
            "Which VisitorCategory this invitation is tagged with — must "
            "resolve to an active category in the resolved tenant. Drives "
            "whether the invitation gets a multi-step approval workflow "
            "snapshotted onto it at submission time."
        ),
    )
    primary_contact: InvitationPrimaryContactCreate
    visitors: list[VisitorSubmit] = Field(default_factory=list)
    visit_details: VisitDetailsSubmit
    carried_items: CarriedItemsSubmit = Field(default_factory=CarriedItemsSubmit)
    vehicles: list[VehicleSubmit] = Field(default_factory=list)
    # Referenced by the consent field's id, never by key/label
    # (restructure-walkin-payload-by-field-id) — one entry per Consent
    # Agreement field the calling branch's published form currently
    # declares. Which ids must be `accepted: true`, and that no `fieldId`
    # outside the branch's configured set is present, is checked
    # dynamically in `invitations/service.py::create_invitation`, not by
    # this schema — omitting `consents` entirely is treated the same as
    # submitting `[]`; a required-consent or unknown-field-id violation is
    # a 422 raised by that dynamic check, not by this field being unset.
    # `max_length` here is only a coarse, static DoS-shaped-payload guard,
    # not the actual allow-list enforcement.
    consents: list[ConsentValue] = Field(default_factory=list, max_length=50)
    # Answers for admin-authored fields on Visit Details, Carried Items,
    # Consent Agreement, or a custom step (add-generic-custom-field-
    # support) — every step with no per-entity structure of its own, so its
    # custom fields are answered once per invitation. Referenced by field
    # id (restructure-walkin-payload-by-field-id), same posture as
    # `consents`: validated dynamically against the effective form in
    # `invitations/service.py::create_invitation`, not by this schema.
    custom_fields: list[CustomFieldValue] = Field(default_factory=list, max_length=50)
    # Per-instance answers for any admin-defined repeatable field group on a
    # step other than Visitor Info/Vehicle Info (add-repeatable-field-
    # groups) — referenced by group id, an ordered list of that group's
    # answer maps, one per submitted instance, each map itself referenced
    # by field id (restructure-walkin-payload-by-field-id). Validated
    # dynamically against the effective form's group definitions (min/max
    # instance count, and each instance's own field values) in
    # `invitations/service.py::create_invitation`, not by this schema.
    groups: list[FieldGroupSubmit] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _check_visitor_list_matches_registration_type(self) -> Self:
        """An Individual registration must not list additional visitors. How
        many visitors a Group registration needs is the Visitor Info group's
        own configured min/max instances (Form Builder), enforced in
        `invitations/service.py::create_invitation`, not hardcoded here.
        """
        if self.registration_type == RegistrationType.individual and self.visitors:
            raise ValueError("An individual registration must not list additional visitors")
        if self.effective_branch_id is None:
            raise ValueError("visitDetails.branchId is required")
        if self.effective_building_id is None:
            raise ValueError("visitDetails.buildingId is required")
        _consents_to_dict(self.consents)
        _custom_fields_to_dict(self.custom_fields, scope="the invitation's customFields")
        _groups_to_dict(self.groups)
        return self

    @property
    def effective_branch_id(self) -> uuid.UUID | None:
        return self.visit_details.branch_id or self.branch_id

    @property
    def effective_building_id(self) -> uuid.UUID | None:
        return self.visit_details.building_id or self.building_id

    @property
    def consents_dict(self) -> dict[str, bool]:
        return _consents_to_dict(self.consents)

    @property
    def custom_field_values(self) -> dict[str, Any]:
        return _custom_fields_to_dict(self.custom_fields, scope="the invitation's customFields")

    @property
    def group_values(self) -> dict[str, list[dict[str, Any]]]:
        return _groups_to_dict(self.groups)


class InvitationOut(CamelModel):
    id: uuid.UUID
    tracking_id: str
    registration_type: RegistrationType
    source: RegistrationSource
    status: str
    visitor_category_id: uuid.UUID | None
    host_id: uuid.UUID | None = None
    poc_user_id: uuid.UUID | None = None
    poc_role_id: uuid.UUID | None = None
    poc_name: str | None = None
    building_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    department_to_visit: str | None = None
    expires_at: datetime
    submitted_at: datetime | None
    approved_at: datetime | None
    current_approval_step: CurrentApprovalStepOut | None = None
    # Populated only by the check-in/out endpoints (devices spec).
    check_in_device: DeviceBriefOut | None = None
    check_out_device: DeviceBriefOut | None = None
    approval_reverted_at: datetime | None = None
    approval_reverted_by_user_id: uuid.UUID | None = None
    approval_revert_reason: str | None = None
    archived_at: datetime | None = None
    checked_out_automatically: bool = False


class InvitationLookupPrefillOut(CamelModel):
    """`GET /invitations/lookup-by-email`'s prefill shape. `photo_url` is
    always resolved when captured, same as every other invitation response
    (`InvitationOut`, `InvitationListItemOut`) — a face photo isn't gated
    like an identity document in this codebase. `id_proof_url` is `null`
    unless the caller additionally holds `documents:view` at the matched
    invitation's branch — a staff caller looking up *someone else's*
    record needs that permission to see their ID-proof document image, not
    just `invitations:create` (`add-invitation-lookup-by-email/design.md`).
    """

    full_name: str
    phone: str | None
    preferred_contact_method: str
    visitor_category_id: uuid.UUID | None
    id_proof_type: str | None
    photo_url: str | None
    id_proof_url: str | None


# --- Employee listing --------------------------------------------------------


class InvitationListItemOut(CamelModel):
    """One row of `GET /invitations` — enough to identify and triage an
    invitation without the per-visitor/vehicle detail
    `InvitationTrackingOut` carries (design.md Decision 2), so a paginated
    list doesn't need to eager-load either child collection.
    """

    id: uuid.UUID
    tracking_id: str
    registration_type: RegistrationType
    source: RegistrationSource
    status: str
    visitor_category_id: uuid.UUID | None
    primary_contact_full_name: str
    primary_contact_email: str | None = None
    primary_contact_phone: str | None = None
    primary_contact_photo_url: str | None = None
    purpose_of_visit: str | None
    department_to_visit: str | None = None
    department_id: uuid.UUID | None = None
    building_id: uuid.UUID | None = None
    expires_at: datetime
    submitted_at: datetime | None
    approved_at: datetime | None
    archived_at: datetime | None = None
    checked_out_automatically: bool = False


# --- add-invitation-export ---------------------------------------------------


class ExportFormat(StrEnum):
    csv = "csv"
    xlsx = "xlsx"


class InvitationExportDateRange(CamelModel):
    """`GET /invitations/export`'s inclusive, tenant-local calendar-date
    range (add-invitation-export/design.md Decision 3) — which timestamp it
    applies to depends on the `status` filter, resolved in the repository.
    """

    date_from: date | None = None
    date_to: date | None = None

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            raise ValueError("dateFrom must not be later than dateTo")
        return self


# --- API-12: public tracking lookup -----------------------------------------


class InvitationVisitorOut(CamelModel):
    """Shared visitor shape for every response *except* the staff detail
    view: public tracking lookup, public tracking-ID check-in
    (`InvitationCheckInOut`), and public QR check-in/check-out
    (`InvitationQrCheckInOut`). Deliberately carries no ID-proof document
    field at all — none of those endpoints has an authenticated caller a
    `documents:view` permission could be checked against, so there must be
    no field here for a future change to accidentally start populating
    (see `enrich-invitation-checkin-and-detail-views/design.md` Decision 3).
    The staff detail view uses `InvitationVisitorDetailOut` instead, which
    adds exactly that field, gated by `documents:view`.
    """

    id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    # Optional (form-builder): whether a co-visitor's ID proof is captured
    # at all is now branch-configurable.
    id_proof_type: str | None
    photo_url: str | None = None
    custom_fields: list[CustomFieldValue]


class InvitationVisitorDetailOut(CamelModel):
    """`GET /invitations/{id}`-only visitor shape — everything
    `InvitationVisitorOut` has, plus `id_proof_url`, resolved only when the
    requesting caller holds `documents:view` (`null` otherwise). See
    `InvitationVisitorOut`'s docstring for why every other response uses
    that schema instead of this one.
    """

    id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    id_proof_type: str | None
    id_proof_url: str | None = None
    photo_url: str | None = None
    custom_fields: list[CustomFieldValue]


class InvitationBranchOut(CamelModel):
    id: uuid.UUID
    name: str
    code: str
    address: str | None
    city: str | None


class InvitationBuildingOut(CamelModel):
    id: uuid.UUID
    name: str
    code: str


class InvitationDepartmentOut(CamelModel):
    """`id`/`code` are `None` when only free-text `departmentToVisit` was
    given and it matched no department record."""

    id: uuid.UUID | None = None
    name: str
    code: str | None = None


class InvitationVehicleOut(CamelModel):
    id: uuid.UUID
    vehicle_type: str
    license_plate: str
    make_model: str | None
    color: str | None
    custom_fields: list[CustomFieldValue]


class InvitationCheckInOut(CamelModel):
    """Response for `PATCH /api/v2/invitations/{trackingId}/check-in`, the
    single staff/desk-facing check-in endpoint (spec.md "Staff Check-In Has
    One Canonical Endpoint" / "Staff Check-In Response Surfaces Full
    Invitation Detail") — every field `InvitationOut` already carries, plus
    everything captured at registration that the public tracking lookup
    (`InvitationTrackingOut`) also returns. No branch/creator/badge/watchlist
    internals — those stay exclusive to `InvitationDetailOut`
    (`GET /invitations/{id}`).
    """

    id: uuid.UUID
    tracking_id: str
    registration_type: RegistrationType
    source: RegistrationSource
    status: str
    visitor_category_id: uuid.UUID | None
    host_id: uuid.UUID | None = None
    poc_user_id: uuid.UUID | None = None
    poc_role_id: uuid.UUID | None = None
    poc_name: str | None = None
    expires_at: datetime
    submitted_at: datetime | None
    approved_at: datetime | None
    current_approval_step: CurrentApprovalStepOut | None = None
    archived_at: datetime | None = None
    checked_out_automatically: bool = False
    check_in_device: DeviceBriefOut | None = None
    check_out_device: DeviceBriefOut | None = None
    primary_contact_full_name: str
    primary_contact_photo_url: str | None = None
    purpose_of_visit: str | None
    host_name_or_email: str | None
    preferred_visit_date: date | None
    preferred_visit_time: time | None
    expected_duration: str | None
    department_to_visit: str | None
    additional_notes: str | None
    carried_items: list[str]
    carried_items_description: str | None
    custom_fields: list[CustomFieldValue]
    groups: list[FieldGroupValuesOut]
    visitors: list[InvitationVisitorOut]
    vehicles: list[InvitationVehicleOut]


class InvitationTrackingOut(CamelModel):
    """Full detail, returned only for a lookup by tracking ID (spec.md
    "Tracking Lookup by ID Returns Everything Captured at Creation") — never
    for the email-based lookup, which returns `InvitationTrackingSummaryOut`
    instead. Since creation now completes the whole visit record in one
    call, there is no transient shell/pending state for a caller to observe.
    """

    tracking_id: str
    status: str
    registration_type: str
    source: str
    visitor_category_id: uuid.UUID | None
    primary_contact_full_name: str
    primary_contact_photo_url: str | None = None
    purpose_of_visit: str | None
    host_name_or_email: str | None
    poc_user_id: uuid.UUID | None = None
    poc_role_id: uuid.UUID | None = None
    poc_name: str | None = None
    preferred_visit_date: date | None
    preferred_visit_time: time | None
    expected_duration: str | None
    department_to_visit: str | None
    additional_notes: str | None
    carried_items: list[str]
    carried_items_description: str | None
    custom_fields: list[CustomFieldValue]
    groups: list[FieldGroupValuesOut]
    expires_at: datetime
    submitted_at: datetime | None
    approved_at: datetime | None
    current_approval_step: CurrentApprovalStepOut | None = None
    archived_at: datetime | None = None
    checked_out_automatically: bool = False
    visitors: list[InvitationVisitorOut]
    vehicles: list[InvitationVehicleOut]


class InvitationTrackingSummaryOut(CamelModel):
    """Minimal shape for the email-based lookup (spec.md "Public Lookup by
    Email Is Rate-Limited and Minimally Revealing") — tracking id and status
    only, nothing that identifies other visitors or exposes documents.
    """

    tracking_id: str
    status: str


# --- add-invitation-lifecycle-actions: staff detail view + lifecycle actions -


class InvitationDetailOut(CamelModel):
    """`GET /invitations/{id}` — everything `InvitationTrackingOut` returns
    plus branch/source/creator and every lifecycle field this capability
    adds (design.md Decision 2). Deliberately a separate schema from
    `InvitationTrackingOut`: that one is served to an unauthenticated public
    caller and must never carry `branchId`/`createdByUserId`/badge/
    watchlist internals.
    """

    id: uuid.UUID
    branch_id: uuid.UUID
    branch: InvitationBranchOut
    building: InvitationBuildingOut | None = None
    department: InvitationDepartmentOut | None = None
    source: RegistrationSource
    created_by_user_id: uuid.UUID | None
    tracking_id: str
    status: str
    registration_type: str
    visitor_category_id: uuid.UUID | None
    primary_contact_full_name: str
    primary_contact_email: str | None = None
    primary_contact_phone: str | None = None
    primary_contact_preferred_contact_method: ContactMethod
    primary_contact_photo_url: str | None = None
    primary_contact_id_proof_type: str | None = None
    primary_contact_id_proof_url: str | None = None
    purpose_of_visit: str | None
    purpose_id: uuid.UUID | None = None
    host_name_or_email: str | None
    host_id: uuid.UUID | None = None
    duration_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    poc_user_id: uuid.UUID | None = None
    poc_role_id: uuid.UUID | None = None
    poc_name: str | None = None
    preferred_visit_date: date | None
    preferred_visit_time: time | None
    previous_preferred_visit_date: date | None = None
    previous_preferred_visit_time: time | None = None
    rescheduled_at: datetime | None = None
    reschedule_count: int = 0
    expected_duration: str | None
    department_to_visit: str | None
    additional_notes: str | None
    carried_items: list[str]
    carried_items_description: str | None
    consents: list[ConsentValue]
    consent_recorded_at: datetime | None = None
    custom_fields: list[CustomFieldValue]
    groups: list[FieldGroupValuesOut]
    expires_at: datetime
    submitted_at: datetime | None
    approved_at: datetime | None
    current_approval_step: CurrentApprovalStepOut | None = None
    denial_reason: str | None
    denied_at: datetime | None
    approval_reverted_at: datetime | None = None
    approval_reverted_by_user_id: uuid.UUID | None = None
    approval_revert_reason: str | None = None
    checked_in_at: datetime | None
    checked_in_by_user_id: uuid.UUID | None
    checked_out_at: datetime | None
    checked_out_by_user_id: uuid.UUID | None
    archived_at: datetime | None = None
    checked_out_automatically: bool = False
    badge_number: str | None
    badge_issued_at: datetime | None
    badge_reprint_count: int
    watchlist_flagged: bool
    watchlist_override_at: datetime | None
    watchlist_override_reason: str | None
    watchlist_override_by_user_id: uuid.UUID | None
    visitors: list[InvitationVisitorDetailOut]
    vehicles: list[InvitationVehicleOut]


class InvitationDenyRequest(CamelModel):
    reason: str = Field(min_length=1, max_length=500)


class InvitationRevertApprovalRequest(CamelModel):
    # Stripped before the length check, so a whitespace-only reason is a
    # 422, not a stored blank (spec.md "Reason is mandatory").
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class InvitationRescheduleRequest(CamelModel):
    preferred_visit_date: date
    preferred_visit_time: time


class InvitationExtendRequest(CamelModel):
    expires_at: datetime = Field(
        description="New expiry — must be strictly later than the invitation's current expiresAt."
    )

    @model_validator(mode="after")
    def _check_timezone_aware(self) -> Self:
        if self.expires_at.tzinfo is None:
            raise ValueError("expiresAt must include a timezone offset")
        return self


class InvitationEditRequest(CamelModel):
    """`PATCH /invitations/{id}/edit` (role-based-invitation-workflow) —
    every field is optional; a caller supplies only the ones changing.
    Deliberately excludes the visitor/co-visitor personal fields,
    `visitorCategoryId`, and the host (`hostId`/`hostNameOrEmail`) — host
    reassignment stays exclusively the `approvals` capability's delegation
    endpoint's job. Unlike creation's accept-but-ignore posture for an
    un-updated client, `extra="forbid"` rejects any of those fields outright
    with a validation error rather than silently ignoring them, since no
    existing client depends on this new endpoint's shape yet.

    `pocUserId`/`pocRoleId` (add-invitation-point-of-contact) are the one
    exception to "visit-detail fields only": unlike the host, the point of
    contact is set directly here, to either a specific person or a role, by
    any caller holding `invitations:approve` at the invitation's branch —
    checked separately from (in addition to) this endpoint's own
    `invitations:edit` gate, since not every `invitations:edit` holder
    should be able to name who visitors are routed to
    (`invitations/service.py::edit_invitation`). At most one of the two may
    be supplied.
    """

    model_config = ConfigDict(extra="forbid")

    purpose_of_visit: str | None = Field(default=None, max_length=255)
    purpose_id: uuid.UUID | None = None
    preferred_visit_date: date | None = None
    preferred_visit_time: time | None = None
    expected_duration: str | None = Field(default=None, max_length=50)
    duration_id: uuid.UUID | None = None
    department_to_visit: str | None = Field(default=None, max_length=255)
    department_id: uuid.UUID | None = None
    building_id: uuid.UUID | None = None
    additional_notes: str | None = Field(default=None, max_length=2000)
    poc_user_id: uuid.UUID | None = None
    poc_role_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _check_poc_not_both(self) -> Self:
        if self.poc_user_id is not None and self.poc_role_id is not None:
            raise ValueError("pocUserId and pocRoleId cannot both be supplied")
        return self


class WatchlistOverrideRequest(CamelModel):
    reason: str = Field(min_length=1, max_length=500)


class InvitationQrCheckInOut(CamelModel):
    """Response for `PATCH /api/v2/invitations/qr/{token}/check-in`
    (`qr-checkin-full-registration-detail` — spec.md "QR Check-In Response
    Surfaces Full Invitation Detail") — everything captured at
    registration, matching `InvitationTrackingOut`'s shape, plus the
    QR-specific fields that lookup doesn't carry (`id`, `checkInStatus`,
    the check-in/out timestamps, primary contact email/phone, `hostId`).
    Deliberately a separate schema from `InvitationOut`: that one carries
    none of this detail at all, and this endpoint's whole point is
    surfacing it without a follow-up lookup.
    """

    id: uuid.UUID
    branch_id: uuid.UUID
    tracking_id: str
    status: str
    check_in_status: str
    check_in_device: DeviceBriefOut | None = None
    check_out_device: DeviceBriefOut | None = None
    registration_type: str
    source: str
    visitor_category_id: uuid.UUID | None
    branch: InvitationBranchOut
    building: InvitationBuildingOut | None = None
    department: InvitationDepartmentOut | None = None
    primary_contact_full_name: str
    primary_contact_photo_url: str | None = None
    primary_contact_preferred_contact_method: ContactMethod
    primary_contact_id_proof_type: str | None = None
    primary_contact_email: str | None
    primary_contact_phone: str | None
    host_id: uuid.UUID | None = None
    host_name_or_email: str | None
    poc_user_id: uuid.UUID | None = None
    poc_role_id: uuid.UUID | None = None
    poc_name: str | None = None
    purpose_of_visit: str | None
    purpose_id: uuid.UUID | None = None
    duration_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    department_to_visit: str | None
    preferred_visit_date: date | None
    preferred_visit_time: time | None
    expected_duration: str | None
    additional_notes: str | None
    carried_items: list[str]
    carried_items_description: str | None
    consents: list[ConsentValue]
    consent_recorded_at: datetime | None = None
    custom_fields: list[CustomFieldValue]
    groups: list[FieldGroupValuesOut]
    submitted_at: datetime | None
    approved_at: datetime | None
    checked_in_at: datetime | None
    checked_out_at: datetime | None
    archived_at: datetime | None = None
    checked_out_automatically: bool = False
    expires_at: datetime
    visitors: list[InvitationVisitorOut]
    vehicles: list[InvitationVehicleOut]


class BadgeOut(CamelModel):
    badge_number: str
    badge_url: str
    issued_at: datetime
    reprint_count: int
