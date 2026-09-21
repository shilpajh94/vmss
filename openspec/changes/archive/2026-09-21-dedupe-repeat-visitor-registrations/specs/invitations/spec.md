## ADDED Requirements

### Requirement: A Returning Primary Contact's Full Name Is Locked to Their Prior Invitation
Before creating an invitation, the system SHALL determine whether the
primary contact is "returning" using two keys, checked in this priority
order:
1. **Email match**: the new request's primary contact email is non-null and
   matches a prior invitation's primary contact email.
2. **Phone fallback**: the new request's primary contact email is null, and
   its primary contact phone matches a prior invitation's primary contact
   phone.

A "prior invitation" for either key includes one in any status —
`approved`, `submitted`, `denied`, `checked_in`, `checked_out`, or
expired. When more than one prior invitation matches a key, the most
recently created one is used.

WHEN an email match or a phone-fallback match is found, the system SHALL
persist that prior invitation's `primaryContactFullName` on the new
invitation, regardless of what value (if any) the new request submits for
it. WHEN no match is found — including when the new request's primary
contact email is non-null but does not match any prior invitation, even if
its phone would have matched a *different* prior invitation — the system
SHALL persist the submitted `primaryContactFullName` exactly as today, with
no change to existing behavior: a non-null, non-matching email always
means "treat as first-time," regardless of what the phone matches.

This lookup and substitution applies identically to `POST /invitations` and
`POST /registrations/walk-in`, since the latter is implemented as a direct
call into the same creation logic. No other field of the new invitation —
`primaryContactPhone` (in the email-match case), ID proof, photo,
`customFieldValues`, `visitorCategoryId`, visit details, carried items,
vehicles, consents, or co-visitors — is affected by this lookup; each is
taken from the new request exactly as it is today. A new `invitations` row
is still created for every invitation request, including this case — this
requirement never causes a request to update or reuse an existing row
instead of creating a new one.

#### Scenario: First time a contact is seen, submitted name is used
- **WHEN** an invitation is created with a primary contact email (or, if no
  email, phone) that has no prior invitation in the tenant's schema
- **THEN** the new invitation's `primaryContactFullName` is exactly the
  value submitted in the request

#### Scenario: Returning email overrides a different submitted name
- **WHEN** an invitation is created with a primary contact email that
  matches a prior invitation whose `primaryContactFullName` is "Priya
  Sharma", and the new request submits `primaryContactFullName` as "Priya
  S."
- **THEN** the new invitation is created with `primaryContactFullName`
  "Priya Sharma", not "Priya S.", and the response reflects the stored
  value

#### Scenario: Returning email's other fields are taken from the new request
- **WHEN** an invitation is created for a returning primary contact email,
  supplying a new phone number, a new `visitorCategoryId`, and new visit
  details
- **THEN** the new invitation stores the newly submitted phone number,
  visitor category, and visit details exactly as submitted — none of them
  are overridden by the prior invitation's values

#### Scenario: A denied or expired prior invitation still counts as a match
- **WHEN** a primary contact's only prior invitation for their email was
  `denied` or has since expired
- **THEN** a new invitation created with that same email still has its
  `primaryContactFullName` locked to that prior invitation's value

#### Scenario: No email submitted falls back to matching by phone
- **WHEN** an invitation is created with a primary contact that supplies a
  phone number but no email, and that phone matches a prior invitation's
  primary contact phone
- **THEN** the new invitation's `primaryContactFullName` is locked to that
  prior invitation's value, the same as an email match

#### Scenario: No email submitted and phone matches nothing is first-time
- **WHEN** an invitation is created with a primary contact that supplies a
  phone number but no email, and that phone matches no prior invitation
- **THEN** the submitted `primaryContactFullName` is used as-is, with no
  lock applied

#### Scenario: A genuinely new email is never overridden by a phone match
- **WHEN** an invitation is created with a primary contact email that does
  not match any prior invitation, even though its phone matches a *different*
  prior invitation belonging to a different email
- **THEN** the new invitation is created from the submitted payload as a
  first-time contact — `primaryContactFullName` and `primaryContactEmail`
  are exactly what was submitted, not locked to the phone-matched
  invitation's values

#### Scenario: A new invitations row is still created for a returning contact
- **WHEN** an invitation is created for a primary contact matched by email
  or by phone fallback
- **THEN** a new, distinct `invitations` row is created for this visit —
  the prior invitation's row is left completely unchanged, and the
  visitor's per-visit history still shows both invitations

#### Scenario: Walk-in registration applies the same lock
- **WHEN** a visitor submits `POST /registrations/walk-in` with a primary
  contact email matching a prior invitation, and a different full name than
  that prior invitation's stored value
- **THEN** the created registration's `primaryContactFullName` is the prior
  invitation's stored value, identical to the behavior for
  `POST /invitations`

#### Scenario: Co-visitors are never matched or locked
- **WHEN** a `group` invitation is created whose primary contact email
  matches a prior invitation, and one of its co-visitors shares an email
  with a person listed as a co-visitor on some earlier invitation
- **THEN** the co-visitor's `fullName` and other fields are stored exactly
  as submitted in this request — no lookup or locking is applied to any
  `invitation_visitors` entry

### Requirement: A Returning Primary Contact Matched by Phone Has Their Email Carried Forward
WHEN a new invitation's primary contact is matched to a prior invitation via
the phone fallback (no email submitted this visit — see "A Returning
Primary Contact's Full Name Is Locked to Their Prior Invitation"), the
system SHALL persist that prior invitation's `primaryContactEmail` on the
new invitation, rather than leaving it null.

#### Scenario: Phone-matched contact's email is populated from history
- **WHEN** an invitation is created with a primary contact that supplies
  only a phone number, and that phone matches a prior invitation whose
  stored `primaryContactEmail` is "priya@example.com"
- **THEN** the new invitation's `primaryContactEmail` is "priya@example.com",
  not null

#### Scenario: An email-matched contact's email is unaffected
- **WHEN** an invitation is created with a primary contact email that
  itself matches a prior invitation
- **THEN** the new invitation's `primaryContactEmail` is the submitted
  email, exactly as today — this requirement changes nothing for the
  email-match case, since the submitted and stored email are already the
  same
