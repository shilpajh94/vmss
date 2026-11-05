## ADDED Requirements

### Requirement: Print is not blocked client-side by ID verification
The system SHALL leave the Print badge action available for an approved visit regardless of `idVerifiedAt`, and SHALL rely on the server's 409 to report missing prerequisites, so tenants that do not require ID verification before printing can print immediately.

#### Scenario: Setting off, ID not verified
- **WHEN** the tenant does not require ID verification before printing and reception prints a visit with no `idVerifiedAt`
- **THEN** the badge is printed

#### Scenario: Setting on, ID not verified
- **WHEN** the server returns 409 `id_not_verified` for a print
- **THEN** the system tells reception to confirm the visitor's physical ID first and the "ID verified" action remains available

### Requirement: Unverified ID is shown as pending
The system SHALL label a search result without `idVerifiedAt` as "ID pending" and one with it as "ID verified", and SHALL keep offering the "ID verified" action while the ID is pending.

#### Scenario: Pending indicator
- **WHEN** a result has no `idVerifiedAt`
- **THEN** the row shows "ID pending" and the "ID verified" action

#### Scenario: Verified indicator
- **WHEN** a result has `idVerifiedAt`
- **THEN** the row shows "ID verified" and no "ID verified" action
