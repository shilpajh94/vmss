## ADDED Requirements

### Requirement: Badge printing is gated by tenant flag and permission
The system SHALL show the Badge printing entry and screen only when `GET /tenants/me` returns `badgePrintFlowEnabled: true` and the signed-in user has the `visitors:print_badge` permission, and SHALL otherwise hide the entry and redirect the route away.

#### Scenario: Flag on and permitted
- **WHEN** a Reception user with `visitors:print_badge` signs in and the tenant flag is on
- **THEN** the Badge printing entry is shown and the screen renders

#### Scenario: Flag off
- **WHEN** the tenant flag is false or absent
- **THEN** no Badge printing entry is shown and navigating to the route redirects away

#### Scenario: Missing permission
- **WHEN** the user lacks `visitors:print_badge`
- **THEN** the entry is hidden and the route is not accessible

#### Scenario: Server reports feature off
- **WHEN** any `/checkin/*` request returns 404
- **THEN** the system shows a neutral "Badge printing is not available" state and not an error toast

### Requirement: Reception can search for a visit
The system SHALL search `GET /checkin/search` with `q`, `page` and `pageSize` and list each result's name, phone, tracking ID, status, check-in status, photo, ID-verified and active-badge indicators, with paging.

#### Scenario: Search by any supported key
- **WHEN** reception enters a name, phone, invitation code, or numeric SMS check-in code
- **THEN** matching visits are listed

#### Scenario: No results
- **WHEN** the search returns no rows
- **THEN** the shared empty state is shown

### Requirement: Reception can confirm physical ID verification
The system SHALL offer an "ID verified" action calling `POST /checkin/{id}/verify-id` and reflect `idVerifiedAt` afterward, and SHALL treat repeated calls as success.

#### Scenario: Verify ID
- **WHEN** reception confirms the physical ID was checked
- **THEN** the row shows ID verified

### Requirement: Reception can print a badge
The system SHALL print via `POST /checkin/{id}/badge` with an `Idempotency-Key` header, reusing the key for network/5xx retries, and SHALL open the returned PDF for printing.

#### Scenario: Successful print
- **WHEN** the visit is approved or checked in, has a photo, and has verified ID, and reception prints
- **THEN** the PDF is opened for printing and the row shows an active badge

#### Scenario: Print blocked by a missing prerequisite
- **WHEN** the response is 409 with `visit_not_approved`, `photo_missing`, or `id_not_verified`
- **THEN** the system states which prerequisite is missing

#### Scenario: Badge already active
- **WHEN** a print returns 409 because a badge is active
- **THEN** the system directs reception to Reprint

### Requirement: Reprint requires a confirmed reason
The system SHALL reprint via `GET /checkin/{id}/badge?reason=` only after an explicit confirm dialog with a required reason of 1-255 characters that warns the previous badge stops working, and SHALL NOT prefetch or auto-call it.

#### Scenario: Confirmed reprint
- **WHEN** reception enters a reason and confirms
- **THEN** the new PDF is opened for printing and the old badge is shown as replaced

#### Scenario: Invalid reason
- **WHEN** the reason is empty or over 255 characters
- **THEN** confirm is disabled

#### Scenario: Reprint before first print
- **WHEN** the server returns 409 because no badge was printed
- **THEN** the system directs reception to Print

### Requirement: Reception can upload a missing photo
The system SHALL show an "Upload photo" action on a search result whose `hasPhoto` is false, upload the chosen JPEG or PNG via `POST /checkin/{id}/photo`, and refresh the row so printing is no longer blocked by `photo_missing`.

#### Scenario: Upload clears the missing photo
- **WHEN** reception uploads an image for a visit with no photo
- **THEN** the row shows "Photo captured" and the action disappears

#### Scenario: Photo already captured
- **WHEN** the server returns 409 `photo_already_captured`
- **THEN** the system tells reception the visit already has a photo and refreshes the row
