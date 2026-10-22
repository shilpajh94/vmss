## ADDED Requirements

### Requirement: Tracking Status Reflects the Invitation Lifecycle the API Reports
The tracking page SHALL map every status the API returns (`submitted`,
`approved`, `denied`, `checked_in`, `checked_out`, `archived`) to a distinct
label, tone and timeline position:
- `denied` SHALL use the error tone;
- `checked_in` and `checked_out` SHALL advance the timeline past
  "Approved";
- `archived` SHALL read as an expired or closed request.

An unrecognised status SHALL show its raw value in a neutral tone rather
than resetting the timeline.

#### Scenario: Denied request
- **WHEN** a visitor looks up a request whose status is `denied`
- **THEN** it is labelled as denied, in the error tone

#### Scenario: Checked-out visit
- **WHEN** a visitor looks up a request whose status is `checked_out`
- **THEN** the timeline shows every step through check-out as complete

#### Scenario: Track input does not zoom on phones
- **WHEN** a visitor focuses the tracking-ID input at 375px wide
- **THEN** the page does not zoom, and pressing Enter submits the lookup

## REMOVED Requirements

### Requirement: Email-based lookup is presented but not yet functional
**Reason**: A permanently disabled control is dead UI. Email lookup will
need an OTP proof once the API's public-endpoint hardening is enforced, so
it gets designed together with that, not wired up as-is.
**Migration**: None for visitors. Tracking by ID is unchanged.
