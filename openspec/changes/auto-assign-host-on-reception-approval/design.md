## Context

`CurrentApprovalStep.totalSteps === 1` (reception-only) is the case where `VisitRequestCard`'s plain "Approve" button applies (`canApprove = isReceptionApprovalStep && (totalSteps ?? 0) <= 1`, `src/presentation/components/invitation-board/VisitRequestCard.tsx:79`) — as opposed to "Approve & Delegate", which is how a multi-step workflow's Reception level assigns the next level's host today. A single-step workflow has no delegate step at all, so there is currently no path, ever, that sets a host on these invitations.

`approveStep` (`src/infrastructure/visit-request-summary-repository.ts:85-95`) calls `POST /invitations/:invitationId/approval-steps/:stepId/approve` and parses only `InvitationActionResultSchema = { success, message }` — no invitation or host data comes back. Setting `hostId`/`hostNameOrEmail` outside the dedicated Delegate endpoint is rejected by the backend (`extra="forbid"`, per the repository comment at `src/data/repositories/visit-request-summary-repository.ts:4-8`).

## Goals / Non-Goals

**Goals:**
- Document the desired behavior (reception-only approval sets host = approver) as a formal requirement, so it's tracked and not lost.
- Make the backend dependency explicit and specific enough to hand to backend work, rather than leaving it as an ad hoc chat request.

**Non-Goals:**
- No frontend implementation in this change — there is nothing the frontend can correctly do without a backend contract to call.
- No change to multi-step workflows or the existing Delegate flow.

## Decisions

**Treat this as blocked, matching the precedent set by `preview-next-approver-on-reception-step`**, which explicitly called out an equivalent gap ("Assign & Approve" for no-workflow invitations) as out of scope for the same reason: "requires a backend capability ... that does not exist today." This change makes that gap a first-class, named proposal instead of a footnote in an unrelated change.

**Two possible backend shapes, either would unblock this (decision deferred to backend):**
1. `approveStep`'s response gains a `data` payload (e.g. the updated `InvitationDetail`, or minimally `{ hostId, hostNameOrEmail }`) when the approved step was the workflow's only step, and the frontend sets it locally / re-fetches `getDetail`.
2. `approveStep` itself, server-side, sets the host to the approving user for single-step invitations, and the frontend simply re-fetches `getDetail` afterward (no client-side field-setting needed at all) — this requires no schema change on the frontend, only a backend behavior change.

Option 2 requires no frontend schema/contract change at all (the frontend already re-fetches `getDetail` after every approve action), so it is the lower-effort path once backend capability exists — noted here so backend can pick either without a follow-up frontend spec.

## Risks / Trade-offs

- **Ambiguity for edge cases** (e.g. a single-step invitation approved by someone who is not literally "Reception" role, if that ever becomes possible) is out of scope until `lock-workflow-level-one-to-reception` is the enforced state everywhere — this change assumes that constraint holds.
- **No frontend tasks are actionable yet.** `tasks.md` reflects this: it verifies nothing is silently attempted client-side that can't actually work against today's API.
