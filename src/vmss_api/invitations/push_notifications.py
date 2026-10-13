"""Builds the staff-facing push-notification title/body/data for each
invitation/approval lifecycle event (add-invitation-push-notifications).
The one place enforcing specs/notifications/spec.md's "Push Payloads
Exclude Sensitive Visitor Data" rule — every payload is built from
`primary_contact_full_name`/`tracking_id`/`id` only, never a relationship
(`.visitors`, ID-proof storage keys) that could carry ID-proof/identity-
document data, so it can't be bypassed per call site.
"""

from vmss_api.invitations.models import Invitation


def _build(invitation: Invitation, *, title: str, action: str) -> tuple[str, str, dict[str, str]]:
    body = f"{invitation.primary_contact_full_name} — tracking ID {invitation.tracking_id}"
    data = {
        "invitationId": str(invitation.id),
        "trackingId": invitation.tracking_id,
        "action": action,
    }
    return title, body, data


def step_awaiting_approval(invitation: Invitation) -> tuple[str, str, dict[str, str]]:
    return _build(
        invitation, title="Invitation awaiting your approval", action="step_awaiting_approval"
    )


def approved(invitation: Invitation) -> tuple[str, str, dict[str, str]]:
    return _build(invitation, title="Invitation approved", action="approved")


def denied(invitation: Invitation) -> tuple[str, str, dict[str, str]]:
    return _build(invitation, title="Invitation denied", action="denied")


def approval_reverted(invitation: Invitation) -> tuple[str, str, dict[str, str]]:
    return _build(invitation, title="Invitation approval reverted", action="approval_reverted")


def rescheduled(invitation: Invitation) -> tuple[str, str, dict[str, str]]:
    return _build(invitation, title="Visit rescheduled", action="rescheduled")


def checked_in(invitation: Invitation) -> tuple[str, str, dict[str, str]]:
    return _build(invitation, title="Visitor checked in", action="checked_in")


def checked_out(invitation: Invitation) -> tuple[str, str, dict[str, str]]:
    return _build(invitation, title="Visitor checked out", action="checked_out")


def edited(invitation: Invitation) -> tuple[str, str, dict[str, str]]:
    return _build(invitation, title="Visit details updated", action="edited")


def host_assigned(invitation: Invitation) -> tuple[str, str, dict[str, str]]:
    """role-based-invitation-workflow: sent to whoever the invitation's
    ownership step is delegated to — the newly resolved host, distinct from
    `step_awaiting_approval` (sent to every holder of the owning role before
    anyone has been named).
    """
    return _build(invitation, title="You've been named host", action="host_assigned")


def poc_assigned(invitation: Invitation) -> tuple[str, str, dict[str, str]]:
    """add-invitation-point-of-contact: sent to the newly named point of
    contact — a specific user (`notifications_service.notify_user`) or every
    holder of a role at the invitation's branch
    (`notifications_service.notify_role_at_branch`), via
    `notify_step_approver`'s existing user-XOR-role routing
    (`invitations/service.py::edit_invitation`). Distinct from
    `host_assigned`: the host is who the visitor is meeting; the point of
    contact is who to reach about the visit's logistics — the invitation may
    have either, both, or neither resolved at any given time.
    """
    return _build(invitation, title="You've been named point of contact", action="poc_assigned")
