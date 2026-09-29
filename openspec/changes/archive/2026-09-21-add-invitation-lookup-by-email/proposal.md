## Why

The staff "Register Visitor" wizard wants to auto-fill Primary Contact fields
(name, phone, preferred contact method, visitor category, ID-proof type) when
the staff member types an email address matching a visitor who has a prior
invitation on file, so front-desk/reception staff don't re-key details for a
repeat visitor. No endpoint today lets an authenticated staff caller look up
a visitor's most recent profile by email — `GET /visitor-portal/me` exists
for exactly this purpose but is gated by the OTP `identity_verified` proof
token, which only a self-service visitor (not a staff member on their
behalf) can obtain.

## What Changes

- Add `GET /invitations/lookup-by-email?email=<email>` — a staff-authenticated
  (session token, same as other `/invitations` routes), branch-scoped lookup
  returning a prefill payload built from the most recent non-deleted
  invitation whose primary contact email matches, case-insensitively.
- Response is `data: null` (200, not 404) when no match — same
  "no match is a normal case, not an error" convention `visitor_return_visit`
  already established, so the frontend can treat it as a silent no-op.
- Prefill payload: `fullName`, `phone`, `preferredContactMethod`,
  `visitorCategoryId`, `idProofType`, `photoUrl`, `idProofUrl`. Follows the
  exact same visibility convention `GET /invitations/{id}`
  (`InvitationDetailOut`) already uses for a staff caller viewing someone
  else's record: `photoUrl` is resolved unconditionally (a face photo isn't
  treated as sensitive as an identity document in this codebase — see
  `InvitationOut`/`InvitationListItemOut`, which already expose it
  ungated), while `idProofUrl` is `null` unless the caller additionally
  holds `documents:view` at the matched invitation's branch
  (`security-architecture.md` §4) — `invitations:create` alone is not
  enough. This was originally scoped to exclude both fields entirely; the
  frontend team asked for them after seeing the first version, and this
  revision adds them under the existing permission boundary rather than a
  new one.
- Gated by `invitations:create` (not `invitations:view`): this lookup only
  exists to prefill the create-invitation wizard, so it should require
  exactly the permission that lets a caller act on the result (create an
  invitation) — a caller who can only view invitations has no create flow to
  prefill. Branch-scoped via the same `require_branch_scope` pattern
  `list_invitations_page` (`GET /invitations`) already uses: no
  `X-Branch-ID` header falls back to every branch the caller holds
  `invitations:create` at; an explicit header narrows to that one branch (or
  403/404s per the existing helper's rules).
- New `InvitationRepository` method for a case-insensitive latest-match
  query, branch-scoped — a new method rather than changing
  `get_latest_by_primary_contact_email`'s existing case-sensitive,
  unscoped behavior, since that method backs the create-time
  duplicate-registration lock (`dedupe-repeat-visitor-registrations`) and
  changing its matching/scoping semantics is a separate decision this change
  does not make.
- **Not** using the frontend's originally-requested path
  (`GET /staff/visitors/lookup`): no route in this API uses a `/staff` URL
  prefix — staff-only routes live under their own feature prefix and are
  distinguished by their auth dependency chain, not the URL
  (`fastapi-architecture.md` §7, `project-rules.md`'s directory structure).
  This lives under the existing `/invitations` prefix instead, consistent
  with every other staff-facing invitations route.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `invitations`: adds a new requirement, "Staff Looks Up a Visitor's Prefill
  Data by Email", to the existing capability — an additive endpoint, no
  existing requirement's behavior changes.

## Impact

- `src/vmss_api/invitations/router.py` — new `GET /lookup-by-email` route.
- `src/vmss_api/invitations/service.py` — new
  `get_prefill_by_email(tenant_db, email, branch_scope)`.
- `src/vmss_api/invitations/repository.py` — new case-insensitive,
  branch-scoped latest-match-by-email method.
- `src/vmss_api/invitations/schemas.py` — new `InvitationLookupPrefillOut`
  (now including `photoUrl`/`idProofUrl`).
- `src/vmss_api/invitations/tests.py` — happy path, no-match, case-
  insensitivity, permission-denied, branch-isolation, and
  `documents:view`-gating cases (`testing-standards.md` §2).
- `docs/features/invitations.md` — endpoint documentation.
- No migration, no new table, no new permission code (reuses
  `invitations:create`).
