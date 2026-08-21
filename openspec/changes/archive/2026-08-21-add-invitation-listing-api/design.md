## Context

See proposal.md - Why. This is a straightforward additive list endpoint on
an existing feature (`invitations`) that already has a tenant-scoped,
branch-owning model (`Invitation.branch_id`) and an established list-endpoint
pattern to follow: `org_structure`'s `list_buildings`/`list_floors`, which
use `require_branch_scope(permission_code)` (`org_structure/deps.py`) to
resolve either one authorized branch (`X-Branch-ID` present) or the caller's
full authorized-branch set (`X-Branch-ID` absent), then filter a paginated
query by that `BranchScope`. `TenantScopedRepository.paginate` (`core/
database.py`) already provides the shared count+page-query primitive
`org_structure/repository.py`'s various `list_page` methods build on.

## Goals / Non-Goals

**Goals:**
- Reuse the existing branch-scope, pagination, sorting, and response-envelope
  patterns exactly as `org_structure` implements them — no new primitives.
- Keep the list response lightweight (one row shape, no eager-loaded
  visitors/vehicles) since a listing view is for triage/browsing, not detail.

**Non-Goals:**
- No new filter dimensions beyond `status`/`registrationType`/`source`
  (e.g. no free-text search, no date-range filter) — not asked for, easy to
  add later as an additive query param if needed.
- Not replacing or changing `GET /invitations/track`'s existing behavior.

## Decisions

**Decision 1: Reuse `require_branch_scope`, not a new dependency.**
`require_branch_scope("invitations:view")` (already defined in
`org_structure/deps.py`, already imported by `org_structure/router.py`) is
generic over any permission code — nothing invitations-specific needs to be
added to it. Alternative considered: give `invitations` its own copy of the
same logic; rejected, since the whole point of the existing helper is to
have this branch-scope-resolution logic in exactly one place.

**Decision 2: New `InvitationListItemOut` schema, not reuse of
`InvitationTrackingOut`/`InvitationOut`.**
`InvitationTrackingOut` eager-loads and serializes `visitors`/`vehicles` —
fine for a single-invitation lookup, wasteful (and a query-performance.md
§1 violation risk if not eager-loaded per row) across a paginated list.
`InvitationOut` (returned by `POST /invitations`) is close but omits fields
a list/triage view needs (primary contact name, purpose of visit) that
`InvitationTrackingOut` has. A dedicated `InvitationListItemOut` carries
exactly the list-appropriate field set; the repository's `list_page` query
does not `selectinload` visitors/vehicles at all, since nothing in the
response needs them.

**Decision 3: `sortBy` whitelist mirrors `submittedAt`/`createdAt` only.**
Matches `BranchRepository.list_page`'s pattern of mapping a small
`Literal`/enum of sortable field names to actual ORM columns
(`org_structure/repository.py`). `submittedAt` is the default since that's
the timestamp staff care about for "who's expected when," with `createdAt`
as the fallback for administrative/audit browsing.

**Decision 4: Filters are three independent, optional, exact-match query
params.** `status: str | None`, `registrationType: RegistrationType | None`,
`source: RegistrationSource | None` — each an explicit typed param
(api-conventions.md §1), combined with AND when more than one is supplied.
`status` stays a plain optional `str` (not an enum) since `Invitation.status`
is a free-form column with values (`submitted`, and reserved
`cancelled`/`expired`) that aren't yet formalized as an enum anywhere else
in the codebase (`invitations/models.py`'s own docstring notes this).

## Risks / Trade-offs

- [Risk] A tenant with a large invitation volume and a company-wide-scoped
  caller (`X-Branch-ID` omitted) could return a very large `total` across
  many branches → Mitigation: existing `page`/`pageSize` (max 100) cap this
  the same way it already caps every other list endpoint; no different risk
  profile than `GET /branches` today.
- [Trade-off] No free-text search in this pass → acceptable per proposal
  scope; can be added later as an additive query param without a breaking
  change (api-conventions.md §2).
