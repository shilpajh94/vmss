## Why

Every invitation/registration today stores the primary contact's identity
(`fullName`, `email`, `phone`, ID proof, photo, custom-field answers) as a
fresh, independent copy on each new `Invitation` row — there is nothing
tying two visits by the same person together. A visitor who has registered
before has no way to avoid re-typing their name and re-entering their
contact details on every subsequent visit, and nothing in the system
recognizes them as the same person across visits.

## What Changes

- `create_invitation` (shared by staff pre-registration `POST /invitations`
  and visitor walk-in `POST /registrations/walk-in` — the walk-in endpoint
  already forwards to it unchanged) SHALL, before creating a new
  invitation, resolve whether the submitted primary contact is "returning"
  using two keys, in priority order:
  1. **Email match**: the submitted email is non-null and matches a prior
     invitation's primary contact email.
  2. **Phone fallback**: the submitted email is null (not provided this
     visit), and the submitted phone matches a prior invitation's primary
     contact phone.
- **First time this contact is seen** (neither key matches — including the
  case where an email *is* submitted but doesn't match any prior
  invitation, even if the phone would have): behavior is unchanged — the
  invitation is created from the submitted payload exactly as today. A
  submitted email that doesn't match history always wins over a phone that
  would have matched — see "genuinely new email" below.
- **Returning primary contact** (email match, or phone fallback per above):
  - The system still creates a brand-new `invitations` row for this visit —
    per-visit history/audit trail (`security-architecture.md` §5, the
    `emergency` "who's inside" report) is completely unaffected. No new
    table, no change to `invitation_visitors`, no change to what counts as
    a separate "visit."
  - `fullName` is locked: the new row's `primaryContactFullName` is always
    carried forward from the matched prior invitation, regardless of what
    the request submits for it.
  - `email` is locked the same way: on an **email match**, the submitted
    email already equals the stored one, so nothing changes there. On a
    **phone fallback** match (no email submitted this visit), the new row's
    `primaryContactEmail` is populated from the matched prior invitation's
    stored email, rather than being left null — so a returning visitor who
    only re-enters their phone still gets their known email carried
    forward.
  - Every other primary-contact field this request actually supplies
    (`phone` when an email match was used, `preferredContactMethod`, ID
    proof type/file, photo, `customFieldValues`) is written to the new row
    from this submission, the same as today — nothing here is locked or
    defaulted from history.
  - Everything that is inherently per-visit — `visitorCategoryId`, visit
    details, carried items, vehicles, consents, co-visitors
    (`invitation_visitors`) — is taken from this submission exactly as it is
    today.
- **Genuinely new email is always a fresh identity, even if the phone
  matches history**: WHEN a submission includes an email that does not
  match any prior invitation, it is treated as first-time — regardless of
  whether the submitted phone matches a *different* prior invitation's
  phone. The phone fallback (point 2 above) only ever applies when no email
  is submitted at all. This is a deliberate design choice, not an edge case
  to fix later: it's how a visitor "edits" their email — by registering
  under the new one — without ever silently merging two different email
  identities together.
- **BREAKING**: a caller submitting a different `fullName` for an
  already-seen contact no longer gets that name recorded — the prior name
  is silently retained instead. Response payloads for such a request now
  echo back the *stored* `fullName` (and, for a phone-fallback match, the
  *stored* `email`), not what was submitted.
- `POST /registrations/walk-in` inherits this behavior automatically,
  without its own code or spec change, because it already funnels through
  `create_invitation` and the `registrations` capability's existing
  requirement is that it mirrors invitation creation's contract exactly.

### Explicit assumptions (please correct if wrong)
- This applies only to the **primary contact**. Co-visitors
  (`invitation_visitors`) are completely out of scope — every group
  registration still creates fresh co-visitor rows exactly as today, with no
  matching, locking, or carry-forward logic of any kind.
- "Prior invitation" match includes a prior invitation in *any* status
  (`approved`, `submitted`, `denied`, `checked_in`, `checked_out`, expired) —
  even a denied or long-expired one still counts as "this contact has
  visited before" for the purpose of locking `fullName`/`email`.
- If the submitted phone (with no email given) matches more than one prior
  invitation with different stored emails/names, the most recent one wins —
  same "most recent" tie-break as the email-match case.
- ID proof and photo capture requirements are unchanged — a returning
  primary contact still supplies them on every visit exactly as required
  today (branch-configured); this change does not introduce any "skip
  re-upload" behavior.

## Capabilities

### Modified Capabilities
- `invitations`: `create_invitation`'s handling of the primary contact's
  `fullName` (and, for a phone-fallback match, `email`) changes for a
  returning contact — locked to the value from that contact's most recent
  prior invitation rather than accepting whatever the new request submits
  (or leaving `email` null).

## Impact

- **Code**: `src/vmss_api/invitations/service.py::create_invitation` (the
  lookup + name/email substitution) and
  `src/vmss_api/invitations/repository.py` (two "most recent prior
  invitation" lookups — by primary contact email, and by primary contact
  phone — built on/alongside the existing `list_by_primary_contact_email`).
- **No new table, no migration**: `invitations.primary_contact_email` is
  deliberately *not* made unique — many invitations legitimately share one
  email over time (one row per visit, as today). This is pure service-layer
  logic reusing an existing indexed column
  (`Invitation.primary_contact_email`, already indexed for the tracking
  lookup).
- **`registrations`**: no code change — inherits via
  `create_invitation`, consistent with that capability's existing "identical
  payload contract" requirement.
- **Tests**: `invitations/tests.py` gains coverage for the
  first-time-vs-returning-email paths (`testing-standards.md` §2); no new
  permission or tenant-isolation case is needed since this doesn't touch
  RBAC or tenancy.
