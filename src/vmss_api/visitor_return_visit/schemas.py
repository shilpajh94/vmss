from datetime import date

from vmss_api.core.schemas import CamelModel, PaginationMeta


class VisitHistoryEntry(CamelModel):
    """One prior visit in a returning visitor's own history — the same
    status-summary shape the existing public tracking-by-email lookup
    already exposes, plus visit date/purpose. See spec.md "Verified
    Identifier's Visit History Is Retrievable".
    """

    tracking_id: str
    status: str
    visit_date: date | None
    purpose: str | None


class ReturningVisitorPrefill(CamelModel):
    """Drawn from the identifier's most recent prior visit. `photo_url` and
    `id_proof_url` follow the same naming already used for a resolved
    document/photo URL everywhere else in this codebase (e.g.
    `InvitationVisitorDetailOut.id_proof_url`, `Invitation...photo_url`) —
    not `form_builder`'s own field keys, since the client that renders this
    payload already has its own fixed mapping onto that dynamic form
    (confirmed by a runtime `photoUrl` contract break when this field was
    briefly renamed — see spec.md "Prefill Payload Is Drawn From the Most
    Recent Prior Visit").

    Both `id_proof_url` and `photo_url` are the visitor's own
    previously-submitted document/photo, returned under the OTP-proven
    `identity_verified` proof token rather than the staff-facing
    `documents:view` permission — this is the visitor viewing their own
    record, not a staff member viewing someone else's.
    """

    full_name: str
    email: str | None
    phone: str | None
    preferred_contact_method: str
    id_proof_type: str | None
    id_proof_url: str | None
    photo_url: str | None


class ReturningVisitorLookupOut(CamelModel):
    history: list[VisitHistoryEntry]
    prefill: ReturningVisitorPrefill | None
    pagination: PaginationMeta
