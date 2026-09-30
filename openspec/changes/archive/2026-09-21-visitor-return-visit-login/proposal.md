## Why

A visitor who has already been through registration/check-in once today has
no way to come back later, prove it's the same person, see their own past
visit(s), or start a new visit without re-typing everything from scratch.
`identity-verification` (API-15) already issues a short-lived, signed
"verified-contact proof" once a visitor confirms an OTP sent to their email or
phone, but nothing in the codebase consumes that proof yet — its own
docstring (`core/security.py::create_identity_verified_token`) flags it as
"not yet consumed by any caller." This change closes that gap: a verified
identifier becomes the key for looking up whether that email/phone has a
prior visit on file and, if so, returning enough of that visitor's own data
to prefill a new registration, without ever giving the visitor a real user
account, a JWT/RBAC session, or access to another visitor's data.

## What Changes

- New unauthenticated, OTP-gated endpoint(s) under a `visitor-portal`
  capability that:
  - Accept an already-issued `identity_verified` proof token (from
    `identity-verification`'s existing `POST /identity-verification/verify`)
    and use it — not a client-supplied identifier — as the sole key for
    every lookup, so a visitor can only ever retrieve data tied to an
    identifier they just proved control of.
  - Return that identifier's own visit history (tracking ID, status, visit
    date/purpose — the same shape the existing public tracking-by-email
    lookup already exposes) scoped to the single default tenant this
    deployment resolves (`core/tenancy.py::resolve_default_tenant`, the same
    posture `identity-verification` and `registrations` already use).
  - Return a prefill payload (name, email, phone, preferred contact method,
    ID proof type, ID-proof document URL, photo URL) drawn from that
    identifier's most recent prior `Invitation`/`InvitationVisitor` row,
    field names (`idProofUrl`/`photoUrl`) matching the resolved-URL naming
    already used elsewhere in this API rather than the dynamic
    registration form's own field keys — the client rendering this payload
    has its own fixed mapping onto that form. Both the document and the
    photo are the identifier's own previously-submitted files, released
    under the OTP-proven proof token itself rather than the staff-facing
    `documents:view` permission (`security-architecture.md` §4) — that
    permission gates a staff caller viewing someone *else's* document; here
    the visitor is viewing their own, with no staff caller involved at all.
- No change to `POST /registrations/walk-in` or `POST /invitations` — a
  returning visitor still submits a new visit through the existing walk-in
  endpoint; this change only supplies the data a client can use to prefill
  that form. This keeps the change additive and keeps first-time-visitor
  behavior completely unaffected.
- No new authenticated "visitor account," password, or JWT/RBAC session:
  visitors continue to never appear in `auth`'s user/role system
  (`auth` capability's "The Visitor Role Grants No Access...").

## Capabilities

### New Capabilities
- `visitor-return-visit`: lets a visitor who has verified an email/phone via
  the existing OTP flow retrieve their own prior visit history and a prefill
  payload for a new registration, scoped strictly to the verified identifier.

### Modified Capabilities
(none — `identity-verification`, `registrations`, and `invitations` are
consumed as-is; no requirement in any of them changes)

## Impact

- **New code**: `src/vmss_api/visitor_return_visit/` (`router.py`,
  `service.py`, `schemas.py`, `repository.py`, `deps.py`) — a thin capability
  that depends on `identity_verification` (to validate the proof token) and
  `invitations` (`InvitationRepository`, read-only, to find prior visits by
  contact).
- **`core/security.py`**: no change to token creation; a new
  `decode_identity_verified_token`-style helper (or inline decode +
  `claims["type"] == "identity_verified"` check) is added for this consumer.
- **Rate limiting**: the new endpoints join the existing `slowapi` posture
  for public visitor-facing endpoints (`security-architecture.md` §2).
- **Audit/logging**: read-only lookups are logged per
  `logging-observability.md` (masked identifier, no PII in plaintext); no
  `AuditLog` write is needed since nothing is mutated.
- **No database migration**: this reads existing `Invitation`/
  `InvitationVisitor` rows; no new table.
