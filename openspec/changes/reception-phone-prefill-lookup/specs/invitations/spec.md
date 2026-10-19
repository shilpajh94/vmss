## ADDED Requirements

### Requirement: Staff Looks Up a Visitor's Prefill Data by Phone
`GET /invitations/lookup-by-phone` SHALL accept a caller holding `invitations:create` at a branch and a `phone` query parameter, and SHALL return a prefill payload (`fullName`, `email`, `phone`, `preferredContactMethod`, `visitorCategoryId`, `idProofType`, `photoUrl`, `idProofUrl`) built from the most recent non-deleted invitation, among the branches the caller is authorized for, whose primary contact phone matches the supplied `phone`. Phones SHALL be compared by their digits only, ignoring spaces, hyphens, parentheses and a leading `+`. The response SHALL be `data: null` (`200`, not `404`) when no invitation matches. `phone` SHALL contain at least 7 digits after normalization; a shorter value SHALL be rejected with a validation error. `photoUrl` SHALL be resolved whenever a photo was captured. `idProofUrl` SHALL be `null` unless the caller additionally holds `documents:view` at the matched invitation's branch.

#### Scenario: Matching phone returns the most recent invitation's prefill data
- **WHEN** a caller holding `invitations:create` requests `GET /invitations/lookup-by-phone?phone=9544232271` and two invitations exist under that phone, one older and one newer
- **THEN** `data` reflects the newer invitation's `fullName`, `email`, `preferredContactMethod`, `visitorCategoryId` and `idProofType`

#### Scenario: Formatting differences do not prevent a match
- **WHEN** an invitation is stored with phone `+91 95442-32271` and a caller requests `phone=919544232271`
- **THEN** `data` reflects that invitation

#### Scenario: No matching invitation returns null data
- **WHEN** no invitation at an authorized branch has a matching phone
- **THEN** the response is `200` with `data: null`

#### Scenario: Phone with too few digits is rejected
- **WHEN** a caller requests `phone=123`
- **THEN** the request is rejected with a validation error and no lookup runs

#### Scenario: A match at an unauthorized branch is not returned
- **WHEN** the only matching invitation is at a branch where the caller lacks `invitations:create`
- **THEN** the response is `200` with `data: null`

#### Scenario: X-Branch-ID narrows the lookup
- **WHEN** a caller authorized at several branches sends `X-Branch-ID` for one of them and the match exists only at another
- **THEN** the response is `200` with `data: null`

#### Scenario: Caller without invitations:create is rejected
- **WHEN** a caller holding only `invitations:view` requests this endpoint
- **THEN** the request is rejected with `403`

#### Scenario: ID-proof URL requires documents:view
- **WHEN** the matched invitation has an ID-proof document and the caller lacks `documents:view` at its branch
- **THEN** `idProofType` is present and `idProofUrl` is `null`

#### Scenario: Photo URL is resolved without documents:view
- **WHEN** the matched invitation has a photo and the caller holds `invitations:create` only
- **THEN** `photoUrl` is a fetchable URL

### Requirement: Lookup Prefill Payload Includes Email
The prefill payload returned by both `GET /invitations/lookup-by-email` and `GET /invitations/lookup-by-phone` SHALL include an `email` field holding the matched invitation's primary contact email, or `null` when that invitation has none.

#### Scenario: Phone lookup returns the stored email
- **WHEN** the matched invitation's primary contact email is `jane@example.com`
- **THEN** the phone lookup's `data.email` is `jane@example.com`

#### Scenario: Matched invitation has no email
- **WHEN** the matched invitation was registered with phone only
- **THEN** `data.email` is `null`
