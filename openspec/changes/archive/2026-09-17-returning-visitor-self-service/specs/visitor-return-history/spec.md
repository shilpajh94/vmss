## Purpose

The visitor-return-history capability lets a visitor who has already completed OTP verification see their past visits and start a new visit request pre-filled from their known profile, instead of re-entering details the system already has.

## ADDED Requirements

### Requirement: History is fetched using the OTP proof token
The system SHALL call the visitor-portal lookup with the `proofToken` returned by OTP verification as a bearer credential, and SHALL store that token only in memory or sessionStorage, never in localStorage or in logs.

#### Scenario: Lookup uses the verified session's proof token
- **WHEN** OTP verification succeeds
- **THEN** the system calls the visitor-portal lookup with the returned proof token as the Authorization bearer credential, without persisting the token to localStorage

### Requirement: Return-visit history screen lists past visits
The system SHALL render each past visit's tracking id, status, visit date, and purpose on the return-visit history screen, ordered as returned by the lookup, when the visitor has one or more prior visits.

#### Scenario: Visitor sees prior visits
- **WHEN** the history lookup returns one or more visits
- **THEN** the return-visit history screen lists each visit's tracking id, status, visit date, and purpose

### Requirement: History screen supports paging through results
The system SHALL use the lookup's pagination metadata to let the visitor load further pages of history when more visits exist than fit on the current page.

#### Scenario: Visitor loads more history
- **WHEN** the pagination metadata indicates further visits are available
- **THEN** the system offers an action to load the next page and appends or replaces the list with the results

### Requirement: History screen offers a prefilled new request
The system SHALL render a "Start a new request" action on the return-visit history screen that opens the visitor request wizard pre-filled from the lookup's prefill profile.

#### Scenario: Visitor starts a new request from history
- **WHEN** the visitor activates "Start a new request" on the return-visit history screen
- **THEN** the visitor request wizard renders pre-filled from the prefill profile

### Requirement: ID-proof document image is never returned or prefilled
The system SHALL NOT request, display, or prefill an ID-proof document image from the visitor-portal lookup; only the ID-proof type is prefilled, and the image must be uploaded fresh for the new request.

#### Scenario: ID-proof type prefills but the image does not
- **WHEN** the lookup's prefill profile includes an ID-proof type
- **THEN** the wizard pre-fills the ID-proof type field but requires the visitor to upload a new ID-proof image

### Requirement: Lookup failure is reported without losing the verified session
The system SHALL show an error and let the visitor retry when the visitor-portal lookup fails with 429 (rate limited) or 404 (service misconfigured), without discarding the visitor's completed OTP verification or requiring a fresh code.

#### Scenario: Lookup is rate limited
- **WHEN** the visitor-portal lookup responds with 429
- **THEN** the system shows a rate-limit error and lets the visitor retry the lookup without re-verifying

#### Scenario: Lookup service is misconfigured
- **WHEN** the visitor-portal lookup responds with 404
- **THEN** the system shows an error indicating the service is unavailable and lets the visitor retry without re-verifying
