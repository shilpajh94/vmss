## Context

See proposal.md - Why. The frontend team requested `GET /staff/visitors/
lookup?email=<email>` returning `{fullName, phone, preferredContactMethod,
visitorCategoryId, idProofType}` or `data: null`. Two existing, similar
lookups already inform the design:

- `InvitationRepository.get_latest_by_primary_contact_email`
  (`src/vmss_api/invitations/repository.py`) — case-sensitive, tenant-wide
  (no branch filter), backs the create-time duplicate-registration lock.
- `VisitorReturnVisitRepository.get_most_recent`
  (`src/vmss_api/visitor_return_visit/repository.py`) — same query shape
  against email-or-phone, but serves the unauthenticated OTP-proof-token
  flow, with no branch concept at all (single default tenant, no staff
  caller).

Neither is a branch-scoped, case-insensitive, staff-authenticated lookup, so
this change adds a third, purpose-built query rather than repurposing either.

## Goals / Non-Goals

**Goals:**
- A staff-authenticated, branch-scoped, case-insensitive email lookup
  returning a minimal prefill payload for the create-invitation wizard.
- Reuse the existing `require_branch_scope`/`BranchScope`/`_branch_filter`
  machinery `list_invitations_page` already uses, rather than inventing a
  parallel branch-authorization mechanism.

**Non-Goals:**
- Does not expose `idProofUrl` to a caller lacking `documents:view` at the
  matched invitation's branch — that permission remains the gate for
  viewing someone else's identity document, `invitations:create` alone is
  not enough (revised from this change's first draft, which excluded the
  field entirely; see Decisions below for why it's now included but
  conditionally).
- Does not change `get_latest_by_primary_contact_email`'s existing
  case-sensitive, unscoped behavior used by the dedupe-on-create flow.
- Does not introduce a new permission code — reuses `invitations:create`.
- Does not adopt the frontend's originally-requested `/staff/...` URL
  prefix (see proposal.md's "What Changes" — no such prefix exists anywhere
  in this API).

## Decisions

**Path: `/invitations/lookup-by-email`, not `/staff/visitors/lookup`.**
Every staff-only route in this API lives under its own feature's prefix and
is distinguished by its `Depends()` auth chain, never by a `/staff` URL
segment (confirmed: no route anywhere uses one). Introducing one just for
this endpoint would be a one-off deviation with no other precedent to
extend later. The frontend team already indicated they'd adjust field
names if needed; the path is the same kind of adjustment.

**Permission: `invitations:create`, not `invitations:view`.**
This lookup exists solely to prefill the create-invitation wizard. Gating
it on `invitations:create` means exactly the callers who can act on the
result (submit an invitation) can see it — a caller who can only view
existing invitations (e.g. the `security` role, which holds
`invitations:view`/`checkin`/`checkout` but not `create`) has no
create-invitation flow to prefill, so denying them this lookup is the
least-privilege choice, not an arbitrary one. Mirrors
`create_invitation`'s own `authorize_branch_id(tenant_db, user,
"invitations:create", branch_id)` check.

**Branch scoping: reuse `require_branch_scope`, same as `GET /invitations`.**
Invitations are branch-scoped data throughout this feature; a lookup that
returns another branch's visitor data to a caller who isn't authorized
there would be a scope leak no different in kind from a list endpoint doing
the same. `require_branch_scope("invitations:create")` gives the same
no-header-falls-back-to-every-authorized-branch,
explicit-header-narrows-to-one behavior `list_invitations` already has, via
one shared dependency rather than a new one.

**A new repository method, not a change to `get_latest_by_primary_contact_email`.**
That method's case-sensitive, branch-unscoped matching is deliberate for
its own caller (the create-time dedupe lock, where a duplicate at *any*
branch, matched exactly, is what's being guarded against). Changing its
semantics to serve this endpoint would silently change dedupe behavior as
a side effect of an unrelated feature. The new method,
`get_latest_for_prefill_by_email(email, branch_scope)`, matches
case-insensitively via `func.lower(...)` and applies the same
`_branch_filter(branch_scope)` helper `list_invitations_page` already
uses.

**`photoUrl` unconditional, `idProofUrl` gated by `documents:view` — not
both gated the same way.** The frontend asked for both fields after the
first version shipped without either. Rather than gating both behind
`documents:view`, this mirrors `GET /invitations/{id}`
(`InvitationDetailOut`/`_to_invitation_detail_out`) exactly:
`primary_contact_photo_url` is resolved unconditionally there (and on
every other invitation response — `InvitationOut`, `InvitationListItemOut`
already expose it ungated to any `invitations:view`/`:create` caller),
while `primary_contact_id_proof_url` is resolved only when
`user.has_permission("documents:view", invitation.branch_id)` is `True`.
This codebase's established line is "identity document = sensitive,
gated"; "face photo = ordinary profile data, not gated" — treating a
lookup-by-email caller differently from a detail-view caller for the same
two fields would be an inconsistency with no stated reason, not a
deliberate stricter posture.

**No rate limiting.** Consistent with every other `get_current_user`/
`require_permission`-gated staff route in this API — rate limiting
(`security-architecture.md` §2) is applied to unauthenticated/public
endpoints, never to authenticated staff ones, and this endpoint doesn't
introduce a new exception to that.

## Risks / Trade-offs

- [Frontend already built against `/staff/visitors/lookup`] → Communicated
  back to the frontend team as part of this change; the response shape
  (field names) matches what they requested, only the path and auth model
  differ from their initial assumption, and they've already said they'd
  adjust for either.
- [A tenant with many invitations under one email could make this a
  non-trivial scan] → Same `created_at DESC LIMIT 1` shape as the two
  existing similar queries; `Invitation.primary_contact_email` already has
  an index (`visitor-return-visit-login` change), though a case-insensitive
  `lower(...)` comparison won't use a plain btree index on that column as
  efficiently as an exact match would. Acceptable for now given the other
  two lookups have the same limitation; a functional index on
  `lower(primary_contact_email)` is a follow-up if this proves slow in
  practice, not a blocker for this change.
