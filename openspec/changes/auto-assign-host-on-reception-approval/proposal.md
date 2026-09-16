## Why

For a visitor category whose approval workflow has only one level (Reception, stepOrder 0 — see `lock-workflow-level-one-to-reception`), the invitation's `host` field stays `null` (rendered as "Unassigned — Front Office") for the entire lifecycle unless someone separately runs the "Delegate" action. There is no such thing as delegation in a single-step workflow — Reception's plain "Approve" button is the only action ever taken — so today these invitations simply never get a host. When Reception approves a single-step (reception-only) request, the reception staff member who approved it should become the invitation's host, since they are the person who actually handled the visit end-to-end.

## What Changes

- When a reception-only (single total step) invitation is approved via the plain "Approve" action, the invitation's `hostId`/`hostNameOrEmail` SHALL be set to the approving reception staff member.
- This does not apply to multi-step workflows: Reception's own step in a multi-step workflow already uses "Approve & Delegate" to assign a later-level host explicitly, and is unaffected.

## Capabilities

### Modified Capabilities
- `staff-dashboard`: a reception-only invitation's host is populated by the approving staff member instead of staying unassigned.

## Impact

- **Affected code (blocked — not implemented by this change)**:
  - `src/infrastructure/visit-request-summary-repository.ts` — `approveStep`'s response is parsed with `InvitationActionResultSchema` (`{ success, message }`, `src/domain/entities/visit-request-summary-schema.ts:35-38`), which carries no host/invitation payload back. The backend's `POST /invitations/:invitationId/approval-steps/:stepId/approve` endpoint itself has no documented way to set or report a host on approve.
  - `src/domain/entities/invitation-detail-schema.ts` — `hostId`/`hostNameOrEmail` are excluded from PATCH edits today; the API rejects them with `extra="forbid"` outside the Delegate flow (`src/data/repositories/visit-request-summary-repository.ts:4-8`).
- **Blocked on a backend capability that does not exist today**: either `approveStep` needs to accept/return host assignment for the single-step case, or a new endpoint is needed. This is the same class of gap the `preview-next-approver-on-reception-step` change flagged and explicitly left out of scope ("Assign & Approve" for no-workflow invitations).
- **This change is proposal/spec only.** No frontend code changes are included; `tasks.md` is not actionable until the backend capability exists.
