## MODIFIED Requirements

### Requirement: Prefill Payload Is Drawn From the Most Recent Prior Visit
WHEN a verified identifier has at least one prior visit, the system SHALL
return a prefill payload built from that visitor's most recent prior visit:
full name, email, phone, preferred contact method, ID proof type, ID-proof
document URL (`idProofUrl`), photo URL (`photoUrl`), and visitor category id
(`visitorCategoryId`), when captured. Field names SHALL follow the same
`idProofUrl`/`photoUrl` naming already used for a resolved document/photo URL
elsewhere in this API (e.g. `InvitationVisitorDetailOut`), not any dynamic
form's own field keys — the client rendering this payload has its own fixed
mapping onto the registration form and depends on these exact names
(confirmed by a runtime contract break when an earlier revision used
different names instead). `visitorCategoryId` SHALL be the raw category id
only, following the same id-only convention already used for this field on
every other invitation-facing response (`InvitationOut`,
`InvitationListItemOut`), not a denormalized category name — a client needing
the category's display name resolves it against the existing public
`GET /visitor-categories` listing it already uses to populate its category
picker. The ID-proof document image and photo are the verified identifier's
own previously-submitted files, released under the OTP-proven
`identity_verified` proof token — this is the visitor viewing their own
record, not a staff member viewing someone else's, so
`security-architecture.md` §4's `documents:view` permission (which gates a
*staff* caller's access to someone else's identity document) does not
apply here.

#### Scenario: Prefill uses the most recent visit's contact details
- **WHEN** a verified identifier has two prior visits, an older one under
  the name "J Carter" and a newer one under "John Carter"
- **THEN** the prefill payload's name is "John Carter", drawn from the newer
  visit

#### Scenario: Prefill includes the most recent visit's own ID-proof document
- **WHEN** a verified identifier's most recent prior visit has an ID-proof
  document on file
- **THEN** the prefill payload includes that visit's `idProofType` and a
  fetchable `idProofUrl` for that same document

#### Scenario: Missing photo or ID-proof document is represented as null, not omitted or errored
- **WHEN** the most recent prior visit has no photo, no ID-proof document,
  or neither on file
- **THEN** the prefill payload's `photoUrl`/`idProofUrl` fields are present
  and null for whichever was not captured

#### Scenario: Prefill includes the most recent visit's visitor category
- **WHEN** a verified identifier's most recent prior visit has a
  `visitorCategoryId` set
- **THEN** the prefill payload's `visitorCategoryId` matches that same value

#### Scenario: Missing visitor category is represented as null, not omitted
- **WHEN** the most recent prior visit has no `visitorCategoryId` set
- **THEN** the prefill payload's `visitorCategoryId` field is present and
  null
