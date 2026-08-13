# visitor-track-request Specification

## Purpose

The visitor-track-request capability lets a visitor check the status of a visit request they already submitted, using the tracking ID they were given, without needing an account or login.

## Requirements

### Requirement: Track page is reachable from the landing page's track entry point
The system SHALL render the track-request page at the visit-tracking route the landing page's "Track Request" action navigates to.

#### Scenario: Visitor reaches the track page from the landing page
- **WHEN** a visitor activates "Track Request" on the landing page
- **THEN** the tracking-ID lookup form renders

### Requirement: Visitor looks up a request by tracking ID
The system SHALL let the visitor submit a tracking ID to look up the associated visit request, and SHALL require a non-empty tracking ID before attempting the lookup.

#### Scenario: Empty tracking ID blocks lookup
- **WHEN** the visitor submits the lookup form with no tracking ID entered
- **THEN** the system blocks the lookup and indicates a tracking ID is required

#### Scenario: Lookup is attempted with a tracking ID
- **WHEN** the visitor submits the lookup form with a tracking ID entered
- **THEN** the system attempts to retrieve the visit request associated with that tracking ID

### Requirement: Successful lookup displays the request's status details
The system SHALL, when a tracking ID matches a visit request, display that request's tracking ID, status, requested date, assigned host, total visitor count, and current stage in a 4-stage timeline (Submitted, Under Review, Approved, Visit Day).

#### Scenario: Matching request displays its status
- **WHEN** the visitor looks up a tracking ID that matches an existing visit request
- **THEN** the system displays the tracking ID, a status indicator, requested date, assigned host, total visitor count, and the timeline with the request's current stage distinguished from completed and upcoming stages

### Requirement: Lookup failure is reported without crashing
The system SHALL, when a lookup fails or no request matches the submitted tracking ID, show the visitor an error message and allow retrying without reloading the page.

#### Scenario: No matching request or lookup error
- **WHEN** the visitor looks up a tracking ID that has no matching visit request, or the lookup cannot be completed
- **THEN** the system shows an error message and lets the visitor try again

### Requirement: Email-based lookup is presented but not yet functional
The system SHALL display the alternate "Track via Email" option matching the approved design, but SHALL NOT perform an email-based lookup when activated.

#### Scenario: Track via Email is visible but inert
- **WHEN** the visitor views the tracking-ID lookup form
- **THEN** a "Track via Email" option is visible, and activating it does not perform any lookup
