## Context

`create_invitation` (`src/vmss_api/invitations/service.py:346`) is the
single implementation behind both `POST /invitations` and
`POST /registrations/walk-in` (`registrations/service.py` calls it directly
with `source=RegistrationSource.visitor_walk_in`). It builds a brand-new
`Invitation` row from the submitted payload on every call; nothing today
looks at whether the primary contact has registered before.

`InvitationRepository.list_by_primary_contact_email` already exists
(`invitations/repository.py:507`), backing the public tracking-by-email
lookup (API-12). It queries `Invitation.primary_contact_email` — a column
that is indexed but deliberately **not** unique, since many invitations
legitimately share one email over time (one row per visit).
`Invitation.primary_contact_phone` is also already indexed
(`models.py:84`, for the same return-visit lookup reasoning). This design
reuses both existing indexed columns; no schema change is needed.

See `proposal.md` for motivation and the explicit assumptions this design
is built on (primary-contact-only scope, any-status match, email-primary/
phone-fallback matching key, a non-matching submitted email always wins
over a matching phone).

## Goals / Non-Goals

**Goals:**
- Look up the most recent prior invitation for the submitted primary
  contact email, and lock `primaryContactFullName` to that prior value when
  a match exists.
- Apply identically to both entry points with a single code change, since
  they already share one implementation.
- Zero schema change, zero migration.

**Non-Goals:**
- No new table, no `visitor_id`/`visitor_profile_id` foreign key, no
  normalization of primary-contact identity out of `invitations`.
- No change to `invitation_visitors` / co-visitor handling.
- No change to ID-proof or photo requirements/re-upload behavior.
- No uniqueness constraint on `primary_contact_email` — duplicate emails
  across rows remain expected and required for visit history.

## Decisions

**Decision 1: "Most recent" prior invitation, not "any" or "all."**
When more than one prior invitation exists for an email, use the one with
the latest `created_at` as the source of truth for `primaryContactFullName`.
Rationale: a single, well-defined source avoids ambiguity if a visitor's
name was ever entered inconsistently across old rows (e.g. a typo on visit
2 that was itself carried forward incorrectly) — "most recent" self-heals
within one extra visit, and is the simplest rule to reason about.
Alternative considered: earliest-ever invitation ("original" name) — rejected
because it can never be corrected without a data migration if the very
first invitation had a typo.

**Decision 2: Two new repository methods, not a reuse of `list_by_primary_contact_email` as-is.**
Add `InvitationRepository.get_latest_by_primary_contact_email(email) ->
Invitation | None` and `InvitationRepository.get_latest_by_primary_contact_phone(phone)
-> Invitation | None`, each ordering by `created_at DESC` with `LIMIT 1` at
the database level, rather than calling the existing
`list_by_primary_contact_email` and taking `max(..., key=created_at)` in
Python. Rationale: the existing method is fine for the tracking-lookup use
case (small result sets, already returns everything the caller needs), but
this call happens on the hot path of every invitation creation — fetching
one row via `ORDER BY ... LIMIT 1` is the query-performance.md §2 "never
loop-and-query" posture applied to "never fetch-all-and-filter-in-Python"
too. The phone lookup is only ever called when no email was submitted
(Decision 5), so it's never redundant work alongside the email lookup on
the same request.

**Decision 3: Enforced server-side, not merely a client-side prefill/disable.**
The proposal frames this as "the client won't show the field as editable,"
but the API itself enforces the lock unconditionally — a client that
submits a different `fullName` anyway (buggy client, direct API call, a
stale cached form) still gets the prior name written, never a validation
error. Rationale: matches the confirmed behavior ("the prior name is
silently retained") and keeps the endpoint idempotent-in-spirit — the same
person's name can't drift based on which client or form version submitted
last.
Alternative considered: reject the request with 422 if the submitted name
differs from history — rejected because it would make a perfectly normal
resubmission (e.g. a retry, or a client that doesn't yet know the visitor
is returning) fail for no actionable reason; silently keeping the
authoritative value is strictly less disruptive.

**Decision 4: Where the substitution happens.**
Inside `create_invitation`, immediately after `payload.primary_contact` is
available and before any `Invitation(...)` construction — resolved
`full_name: str` and `email: str | None` locals, sourced from the matched
prior invitation or the payload, used wherever
`payload.primary_contact.full_name`/`.email` would otherwise have been
read. This keeps the change to one function, with no change to
`InvitationCreate` (the request schema) or `InvitationOut` (the response
schema) — the response already echoes back whatever value was persisted.

**Decision 5: Phone is a fallback key, only consulted when no email is submitted.**
The email lookup always runs first when `payload.primary_contact.email` is
non-null; the phone lookup only runs (and can only ever apply its lock)
when that email is null. A submitted email that fails to match history is
never "rescued" by a phone match against a different prior invitation —
per the confirmed rule, a genuinely new email is always treated as a fresh
identity. Rationale: this keeps email as the primary, authoritative
identity key (consistent with the existing tracking-by-email lookup and
`visitor-return-visit-login`'s OTP-verified-identifier model) while still
letting a phone-only submission avoid re-typing a known email — without
ever silently merging two visitors who happen to share a phone (e.g. a
shared reception/family number) but have different, deliberately distinct
email identities.
Alternative considered: always prefer whichever of email/phone matches,
picking the most-recently-created matching invitation across both —
rejected because it can silently merge two different email identities
that happen to share a phone, contradicting the explicit "new email = new
request" rule.

## Risks / Trade-offs

- **[Risk] A visitor legitimately changes their legal name (marriage,
  correction) and can't get it updated through registration** → Mitigation:
  out of scope for this change per the confirmed rule ("editing the name
  means registering under a different email"); if this becomes a real
  complaint, a follow-up change can add an explicit staff-only "correct
  name" action, separate from the public registration path.
- **[Risk] Two different people share an email (a shared front-desk/family
  email) and get merged under one name** → Mitigation: this is an accepted
  trade-off of email-only matching, already implicit in today's tracking
  lookup (`list_by_primary_contact_email`) treating one email as one
  identity; not a new risk this change introduces.
- **[Trade-off] "Most recent" means a single bad submission (typo) persists
  going forward until corrected by a later submission** → acceptable per
  Decision 1; no admin correction path is being added in this change.

## Migration Plan

No database migration. Deploy is a plain code change to
`invitations/service.py` and `invitations/repository.py`; no data backfill,
no feature flag needed since the new behavior only activates on a genuine
repeat-email submission (additive for any never-seen-before email, which is
every existing row today). Rollback is a plain revert.
