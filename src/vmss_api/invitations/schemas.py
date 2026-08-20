import uuid
from datetime import date, datetime, time
from enum import StrEnum
from typing import Self

from pydantic import EmailStr, Field, model_validator

from vmss_api.core.schemas import CamelModel


class RegistrationType(StrEnum):
    individual = "individual"
    group = "group"


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


class IdProofType(StrEnum):
    aadhaar_card = "Aadhaar Card"
    passport = "Passport"
    driving_license = "Driving License"
    other = "Other"


class VehicleType(StrEnum):
    two_wheeler = "2_wheeler"
    four_wheeler = "4_wheeler"
    heavy = "heavy"


class CarriedItemCategory(StrEnum):
    laptop_tablet = "laptop_tablet"
    mobile_phone = "mobile_phone"
    camera_recording_device = "camera_recording_device"
    usb_drive_storage = "usb_drive_storage"
    tools_equipment = "tools_equipment"
    food_beverages = "food_beverages"
    other = "other"


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
    id_proof_type: IdProofType

    @model_validator(mode="after")
    def _check_contact(self) -> Self:
        _require_reachable_contact(self.email, self.phone)
        return self


class VisitDetailsSubmit(CamelModel):
    purpose_of_visit: str = Field(max_length=255)
    host_name_or_email: str = Field(max_length=255)
    preferred_visit_date: date
    preferred_visit_time: time
    expected_duration: str = Field(max_length=50)
    department_to_visit: str = Field(max_length=255)
    additional_notes: str | None = Field(default=None, max_length=2000)


class CarriedItemsSubmit(CamelModel):
    items: list[CarriedItemCategory] = Field(default_factory=list)
    item_description: str | None = Field(default=None, max_length=2000)


class VehicleSubmit(CamelModel):
    vehicle_type: VehicleType
    license_plate: str = Field(max_length=50)
    make_model: str | None = Field(default=None, max_length=255)
    color: str | None = Field(default=None, max_length=50)


class ConsentsSubmit(CamelModel):
    terms_accepted: bool
    data_processing_accepted: bool
    safety_guidelines_accepted: bool

    @model_validator(mode="after")
    def _check_all_accepted(self) -> Self:
        if not (
            self.terms_accepted
            and self.data_processing_accepted
            and self.safety_guidelines_accepted
        ):
            raise ValueError("All consents must be accepted")
        return self


# --- API-09: employee creates a fully completed invitation in one call -----


class InvitationPrimaryContactCreate(CamelModel):
    full_name: str = Field(max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    preferred_contact_method: ContactMethod = ContactMethod.email
    id_proof_type: IdProofType

    @model_validator(mode="after")
    def _check_contact(self) -> Self:
        _require_contact_for_method(self.email, self.phone, self.preferred_contact_method)
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
    primary_contact: InvitationPrimaryContactCreate
    visitors: list[VisitorSubmit] = Field(default_factory=list)
    visit_details: VisitDetailsSubmit
    carried_items: CarriedItemsSubmit = Field(default_factory=CarriedItemsSubmit)
    vehicles: list[VehicleSubmit] = Field(default_factory=list)
    consents: ConsentsSubmit

    @model_validator(mode="after")
    def _check_visitor_list_matches_registration_type(self) -> Self:
        """spec.md "Visitor List Matches Registration Type"."""
        if self.registration_type == RegistrationType.individual and self.visitors:
            raise ValueError("An individual registration must not list additional visitors")
        if self.registration_type == RegistrationType.group and not self.visitors:
            raise ValueError("A group registration must list at least one visitor")
        return self


class InvitationOut(CamelModel):
    id: uuid.UUID
    tracking_id: str
    registration_type: RegistrationType
    source: RegistrationSource
    status: str
    expires_at: datetime
    submitted_at: datetime | None


# --- API-12: public tracking lookup -----------------------------------------


class InvitationVisitorOut(CamelModel):
    id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    id_proof_type: str


class InvitationVehicleOut(CamelModel):
    id: uuid.UUID
    vehicle_type: str
    license_plate: str
    make_model: str | None
    color: str | None


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
    primary_contact_full_name: str
    purpose_of_visit: str | None
    host_name_or_email: str | None
    preferred_visit_date: date | None
    preferred_visit_time: time | None
    expected_duration: str | None
    department_to_visit: str | None
    additional_notes: str | None
    carried_items: list[str]
    carried_items_description: str | None
    expires_at: datetime
    submitted_at: datetime | None
    visitors: list[InvitationVisitorOut]
    vehicles: list[InvitationVehicleOut]


class InvitationTrackingSummaryOut(CamelModel):
    """Minimal shape for the email-based lookup (spec.md "Public Lookup by
    Email Is Rate-Limited and Minimally Revealing") — tracking id and status
    only, nothing that identifies other visitors or exposes documents.
    """

    tracking_id: str
    status: str
