## ADDED Requirements

### Requirement: Staff Looks Up a Visitor's Prefill Data by Email
`GET /invitations/lookup-by-email` SHALL accept a caller holding
`invitations:create` at a branch and an `email` query parameter, and SHALL
return a prefill payload (`fullName`, `phone`, `preferredContactMethod`,
`visitorCategoryId`, `idProofType`, `photoUrl`, `idProofUrl`) built from the
most recent non-deleted invitation, among the branches the caller is
authorized for, whose primary contact email matches the supplied `email`
case-insensitively. The response SHALL be `data: null` (`200`, not `404`)
when no matching invitation exists, consistent with the existing "no prior
visit is a normal case, not an error" convention. `photoUrl` SHALL be
resolved whenever a photo was captured, regardless of the caller's other
permissions — consistent with every other invitation response in this API
already exposing it ungated. `idProofUrl` SHALL be `null` unless the caller
additionally holds `documents:view` at the matched invitation's branch
(`security-architecture.md` §4) — `invitations:create` alone SHALL NOT be
sufficient to see the identity document image.

#### Scenario: Matching email returns the most recent invitation's prefill data
- **WHEN** a caller holding `invitations:create` at a branch requests
  `GET /invitations/lookup-by-email?email=jane@example.com`, and that
  branch has two invitations under that email, one older and one newer
- **THEN** the response's `data` reflects the newer invitation's
  `fullName`, `phone`, `preferredContactMethod`, `visitorCategoryId`, and
  `idProofType`

#### Scenario: Email match is case-insensitive
- **WHEN** an invitation on file has primary contact email
  `Jane@Example.com`, and a caller requests
  `GET /invitations/lookup-by-email?email=jane@example.com`
- **THEN** the response's `data` reflects that invitation

#### Scenario: No matching invitation returns null data, not an error
- **WHEN** a caller requests `GET /invitations/lookup-by-email` with an
  email that matches no invitation at any branch the caller is authorized
  for
- **THEN** the response is `200` with `data: null`

#### Scenario: A match at an unauthorized branch is not returned
- **WHEN** an invitation under the queried email exists only at a branch
  the caller does not hold `invitations:create` at
- **THEN** the response is `200` with `data: null`, not that other
  branch's data

#### Scenario: An explicit X-Branch-ID header narrows the lookup to that branch
- **WHEN** a caller authorized at multiple branches supplies an
  `X-Branch-ID` header naming one of them, and a matching invitation exists
  only at a different authorized branch
- **THEN** the response is `200` with `data: null`, since the lookup is
  narrowed to the named branch only

#### Scenario: Caller without invitations:create is rejected
- **WHEN** a caller holding only `invitations:view` (not
  `invitations:create`) at any branch requests this endpoint
- **THEN** the request is rejected with `403`

#### Scenario: Photo URL is always resolved when captured
- **WHEN** the most recent matching invitation has a photo on file, and
  the caller holds `invitations:create` but not `documents:view`
- **THEN** the response's `photoUrl` is a fetchable URL

#### Scenario: ID-proof URL is null without documents:view
- **WHEN** the most recent matching invitation has an ID-proof document on
  file, and the caller holds `invitations:create` but not `documents:view`
  at that invitation's branch
- **THEN** the response's `idProofType` is present but `idProofUrl` is
  `null`

#### Scenario: ID-proof URL is resolved with documents:view
- **WHEN** the most recent matching invitation has an ID-proof document on
  file, and the caller holds both `invitations:create` and
  `documents:view` at that invitation's branch
- **THEN** the response's `idProofUrl` is a fetchable URL
