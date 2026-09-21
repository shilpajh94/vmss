## Context

See `proposal.md` - Why. Relevant existing pieces this design builds on,
verified in the current codebase:

- `identity_verification/service.py::verify_otp` already returns an
  `OtpVerifyResult.proof_token`, minted by
  `core/security.py::create_identity_verified_token(identifier, channel,
  tenant_id)` — a JWT with `sub=<identifier>`, `type="identity_verified"`,
  a `channel` claim, and a 15-minute expiry. Its docstring already notes
  it has "not yet [been] consumed by any caller in this codebase" — this
  change is that first consumer.
- `core/security.py::decode_token` generically decodes+verifies any of this
  app's JWTs (raising 401 on failure); nothing today branches on `type`
  after decoding, since no other consumer of a non-access/refresh token type
  exists yet.
- Visitor contact/visit data is not a separate "Visitor" master table.
  `Invitation` (primary contact: `primary_contact_email`,
  `primary_contact_phone`, `primary_contact_name`, `preferred_contact_method`
  — plus `InvitationVisitor` rows for co-visitors) is the one place both
  staff-created invitations and visitor walk-in registrations land
  (`registrations/service.py` creates an `Invitation` with
  `source=RegistrationSource.visitor_walk_in`). "Prior visit" therefore means
  "prior `Invitation` row", regardless of which of the two flows created it.
- `core/tenancy.py::resolve_default_tenant` / `settings.default_tenant_slug`
  is the existing single-tenant resolution path `identity_verification` and
  `registrations` both already use for unauthenticated requests with no
  tenant signal.

## Goals / Non-Goals

**Goals:**
- Turn an already-issued, already-verified `identity_verified` proof token
  into (a) that identifier's own prior-visit history and (b) a prefill
  payload for a new registration.
- Guarantee, structurally, that a caller can never retrieve another
  identifier's data — the lookup key comes only from the token's own claims.
- Reuse every existing piece (OTP flow, `Invitation` table, default-tenant
  resolution, rate limiting) rather than introducing a parallel visitor
  identity model.

**Non-Goals:**
- Not building a visitor "account" (no password, no persistent session
  beyond the existing 15-minute proof token, no entry in `auth`'s
  `User`/`Role` tables).
- Not changing `POST /registrations/walk-in` or `POST /invitations` — this
  change is read-only against existing data; actually creating the new visit
  still goes through the existing walk-in endpoint, unmodified, with the
  client supplying the prefilled values it already fetched.
- Not deduplicating/merging visitor identities across a phone *and* an email
  for the same person — a lookup is scoped to exactly the one identifier
  (and its channel) the caller verified, matching how `identity-verification`
  itself treats email and phone as independent identifiers today.
- Not creating a new permission or relaxing `documents:view` itself — a
  staff caller viewing someone else's ID-proof document still needs
  `documents:view`. This flow's exposure of `idProofUrl` is scoped
  entirely to the identifier viewing their own document under their own
  OTP-proven proof token, a different access path, not an exception carved
  into the staff permission.

## Decisions

### Decision 1: New feature package `visitor_return_visit`, not a new module inside `invitations` or `identity_verification`
A dedicated `src/vmss_api/visitor_return_visit/` package (`router.py`,
`service.py`, `schemas.py`, `repository.py`, `deps.py` — per
`fastapi-architecture.md` §1) keeps this capability's own concern (proof-token
gating, prefill shaping) separate from `identity_verification` (OTP
mechanics) and `invitations` (visit-record ownership). Its repository reads
`Invitation`/`InvitationVisitor` directly (read-only) rather than depending
on `invitations.repository.InvitationRepository`'s write-oriented surface;
this mirrors how `registrations/service.py` already imports
`invitations.models.Invitation` directly rather than going through a shared
repository.
**Alternative considered**: add a method to `InvitationRepository` and a
route to `identity_verification/router.py`. Rejected — it would blur two
capabilities' ownership boundaries for a single-purpose lookup, and
`identity_verification`'s docstring already frames proof-token consumption
as a separate concern from OTP issuance.

### Decision 2: Token validation is a dependency, not inline router logic
A `verified_contact` dependency (in `visitor_return_visit/deps.py`) wraps
`core/security.py::decode_token`, additionally checking
`claims["type"] == "identity_verified"` and raising 401 otherwise (a plain
`decode_token` call alone would happily accept a staff access/refresh token,
since today nothing branches on `type`). This is `Depends()`-based per
`fastapi-architecture.md` §6's existing pattern for auth-adjacent
dependencies (`get_current_user`, `require_permission`), even though this
dependency lives in the feature package rather than `core/`, since — unlike
`get_current_user` — it's meaningful only to this one visitor-facing
capability.
**Alternative considered**: extend `core/security.py::decode_token` itself
to accept an expected `type`. Rejected as broader than needed for one
caller; every other consumer of `decode_token` already knows its own
expected type contextually (e.g. `get_current_user` implicitly expects an
access token) without `decode_token` enforcing it centrally.

### Decision 3: Prefill is read-only against the most recent `Invitation`, no new table
"Most recent prior visit" is `SELECT ... WHERE (primary_contact_email = :id
OR primary_contact_phone = :id) AND deleted_at IS NULL ORDER BY created_at
DESC LIMIT 1` against `Invitation`, scoped to the resolved default tenant's
schema. History listing is the same predicate without the `LIMIT 1`,
ordered the same way, paginated per `api-conventions.md` §1. No new
`VisitorProfile`-style table is introduced — the alternative (a
denormalized, upserted-on-each-visit profile table) would need its own
migration, its own consistency-with-`Invitation` story, and buys nothing a
straightforward query doesn't already provide at today's data volume.
**Alternative considered**: a materialized `visitor_profiles` table keyed by
normalized email/phone, upserted on every invitation/registration creation.
Rejected for now as premature — revisit only if this query becomes a
measured hot path (`query-performance.md`'s "don't design for hypothetical
future requirements").

### Decision 4: No coupling added to `POST /registrations/walk-in`
The new endpoint(s) return data; they do not accept or forward a "create the
new visit" request themselves, and `POST /registrations/walk-in` is not
modified to require or even accept a proof token. This keeps the change
purely additive (`api-conventions.md` §2) and leaves first-time-visitor
walk-in behavior untouched. A client (web/kiosk/app) that already fetched
prefill data simply pre-populates the existing walk-in form and submits it
exactly as today.
**Alternative considered**: thread the proof token through to
`POST /registrations/walk-in` so a returning visit is cryptographically
tied to the same verified identifier as the lookup. Rejected for this
change — it would make walk-in registration's contract depend on this new
capability and changes existing, already-shipped behavior; `security-
architecture.md` §2's "fake-entry prevention" is called out there as its
own open product decision, not something to fold in here silently. Left as
a follow-up if the product decides OTP-verified identity should become
mandatory for a *returning* visitor specifically.

## Risks / Trade-offs

- **[Risk] Email/phone matching is exact-string, not fuzzy** — a visitor who
  registered with a typo'd email won't be recognized as returning.
  → Mitigation: acceptable for v1; the visitor falls back to the existing
  first-time walk-in flow, which already works unmodified (no dead end).
- **[Risk] A shared household/company phone number matches multiple
  visitors' invitations** — prefill could surface a different person's name
  under a shared number. → Mitigation: prefill is explicitly a *convenience
  default* the visitor still reviews/edits before submitting via the
  existing walk-in form; nothing here auto-submits a visit.
- **[Trade-off] Proof token's 15-minute expiry** (set by
  `identity_verification`, unchanged here) means a visitor who verifies,
  browses their history, then takes >15 minutes to submit a new
  registration must re-verify. Accepted as consistent with the existing
  token lifetime rather than special-casing this consumer.

## Open Questions

- Whether `POST /registrations/walk-in` should eventually require a proof
  token for returning visitors specifically (Decision 4's noted follow-up)
  is a product call the security-architecture owner should confirm,
  consistent with `security-architecture.md` §2's existing "fake-entry
  prevention... treat as a product decision to confirm" framing. Doesn't
  block this change, since today's walk-in behavior is unaffected either
  way.
