"""Walk-in registration (API-13) deliberately reuses the exact same payload
contract staff pre-registration uses — see
add-walkin-visitor-registration/proposal.md and design.md Decision 2. These
are the same Pydantic models `invitations.schemas` defines; re-exported here
under names that read naturally from this feature's own router/service,
without a second copy of any validator to drift out of sync.
"""

from vmss_api.invitations.schemas import CarriedItemsSubmit as CarriedItemsSubmit
from vmss_api.invitations.schemas import ConsentsSubmit as ConsentsSubmit
from vmss_api.invitations.schemas import InvitationCreate as WalkInRegistrationCreate
from vmss_api.invitations.schemas import InvitationOut as WalkInRegistrationOut
from vmss_api.invitations.schemas import (
    InvitationPrimaryContactCreate as WalkInPrimaryContactCreate,
)
from vmss_api.invitations.schemas import RegistrationSource as RegistrationSource
from vmss_api.invitations.schemas import RegistrationType as RegistrationType
from vmss_api.invitations.schemas import VehicleSubmit as VehicleSubmit
from vmss_api.invitations.schemas import VisitDetailsSubmit as VisitDetailsSubmit
from vmss_api.invitations.schemas import VisitorSubmit as VisitorSubmit

__all__ = [
    "CarriedItemsSubmit",
    "ConsentsSubmit",
    "RegistrationSource",
    "RegistrationType",
    "VehicleSubmit",
    "VisitDetailsSubmit",
    "VisitorSubmit",
    "WalkInPrimaryContactCreate",
    "WalkInRegistrationCreate",
    "WalkInRegistrationOut",
]
