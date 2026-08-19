## Context

See `proposal.md` - Why for the full field-by-field comparison against the
user's two supplied JSON payloads and the audit table. This document covers
the one schema fix and how the test fixtures/assertions close the
verification gap.

**Why `InvitationTrackingOut` is missing fields.** Reading
`invitations/schemas.py`'s history via `add-pre-registration`'s original
design (archived), the tracking-by-id response was modeled around the
fields most useful for a "can I find my invitation" glance (who, when,
where, visitors, vehicles) and the email-lookup's deliberately minimal
sibling shape (`InvitationTrackingSummaryOut`) got most of the design
attention for *not* over-disclosing. `expected_duration`/
`department_to_visit`/`additional_notes`/`carried_items` simply weren't
added to the fuller shape — not a deliberate minimal-disclosure choice
(that's the email-lookup schema's job, not this one's; see
`docs/features/invitations.md`'s own "Minimal disclosure" section, which
only talks about the email-based lookup), just an incomplete field list.

## Goals / Non-Goals

**Goals:**
- Make `GET /invitations/track?trackingId=` actually return everything a
  visitor submitted, matching its own docstring/docs claim of "full
  detail."
- Prove, with assertions (not just reading the code), that every field in
  both of the user's supplied JSON payloads round-trips correctly from
  submission through to both the DB row and the tracking read-back.

**Non-Goals:**
- Changing `POST /invitations` or the self-registration submission's
  request shape, validation rules, or file handling — all already correct
  against both supplied payloads.
- Changing the email-based lookup's minimal-disclosure shape
  (`InvitationTrackingSummaryOut`) — that's an intentional, documented,
  different design point (security-conscious, since it's reachable by
  anyone who knows an email), not the same gap.

## Decisions

### Decision 1: Add the five missing fields to `InvitationTrackingOut` directly

Add `expected_duration`, `department_to_visit`, `additional_notes`,
`carried_items: list[str]`, and `carried_items_description` to
`InvitationTrackingOut`, populated in `router.py::_to_tracking_out` from the
same `Invitation` columns `service.py` already writes.

**Alternative considered**: return the full `Invitation` row via a schema
shared with an internal/admin view. Rejected — this is still the
*public, unauthenticated* tracking endpoint; adding fields it should
disclose is different from removing the boundary between it and an
internal representation. Explicit field-by-field additions keep the
public contract intentional rather than accidentally growing with whatever
the model happens to have.

### Decision 2: Close the verification gap with fixture/assertion changes, not new test functions

The existing success tests already exercise the right scenarios
(individual submission, group submission with visitors+vehicles); what's
missing is assertion depth. Extend `_individual_submission()`/
`_group_submission()` with the `additionalNotes` and fuller vehicle-#2
fields the user's payloads include, and add assertions in the same three
tests (`test_self_register_individual_success`,
`test_self_register_group_success_with_visitors_and_vehicles`, and a new
assertion block in `test_track_by_tracking_id_success`) checking every
field submitted is both persisted and returned correctly.

**Alternative considered**: add a wholly separate
"test_self_register_full_field_fidelity" test duplicating the existing
success tests with deeper assertions. Rejected — that's assertion
duplication with the existing success tests for no reason; deepening the
existing tests' assertions is strictly better since it keeps one source of
truth per scenario (project's own bias against unnecessary duplication).

## Risks / Trade-offs

- [Trade-off] `InvitationTrackingOut` grows by 5 fields, all previously
  submitted but undisclosed — this is more visible to anyone holding a
  tracking ID (still not guessable/public-listable — see
  `security-architecture.md` §2 on signed/time-boxed tokens, which this
  endpoint's tracking ID predates but the token-based registration link
  itself upholds). Accepted: `docs/features/invitations.md` already
  documents this endpoint as intended for the visitor who submitted the
  data, and none of the five fields are more sensitive than what's already
  exposed (visitor names, phone numbers, ID proof *type* — not the
  document itself).

## Migration Plan

- No schema/migration change — `InvitationTrackingOut` is a response
  schema only, backed by existing `Invitation` columns.
- No `.env`/`settings` changes. No new dependencies.
