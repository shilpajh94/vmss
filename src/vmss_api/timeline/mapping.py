from vmss_api.timeline.schemas import TimelineEventType as T

# The only place audit actions are interpreted. Badge print/reprint audit
# actions from the new badge flow (`badge_printed`/`badge_reprinted`) are
# deliberately absent: `badge_prints` is the system of record for those and
# reading both would show every print twice. The legacy PNG badge
# (`invitation_badge_*`) has no `badge_prints` row, so its audit rows count.
AUDIT_ACTION_TO_EVENT: dict[str, T] = {
    "invitation_created": T.invited,
    "walk_in_registration_created": T.invited,
    "invitation_approved": T.approved,
    "invitation_denied": T.denied,
    "invitation_approval_reverted": T.approval_reverted,
    "visit_id_verified": T.id_verified,
    "visit_photo_captured": T.photo_captured,
    "invitation_checked_in": T.checked_in,
    "invitation_qr_checked_in": T.checked_in,
    "invitation_code_checked_in": T.checked_in,
    "invitation_checked_in_public": T.checked_in,
    "badge_checked_in": T.checked_in,
    "badge_re_entered": T.checked_in,
    "invitation_checked_out": T.checked_out,
    "invitation_qr_checked_out": T.checked_out,
    "invitation_code_checked_out": T.checked_out,
    "invitation_auto_checked_out": T.checked_out,
    "badge_checked_out": T.checked_out,
    "invitation_badge_issued": T.badge_printed,
    "invitation_badge_reprinted": T.badge_reprinted,
}

# `entity_type` is written as both spellings across the codebase.
INVITATION_ENTITY_TYPES = ("Invitation", "invitation")
