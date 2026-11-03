## ADDED Requirements

### Requirement: Timeline is visible only with the timeline:view permission
The invitation detail modal SHALL show the visit timeline only to users holding `timeline:view`.

#### Scenario: Permitted user
- **WHEN** a user with `timeline:view` opens an invitation's detail
- **THEN** the timeline events are requested and listed

#### Scenario: User without the permission
- **WHEN** a user without `timeline:view` opens an invitation's detail
- **THEN** no timeline request is made and the section falls back to the existing timestamp summary

### Requirement: Timeline loads from the correct endpoint
The client SHALL request `GET /invitations/{invitationId}/timeline` for an invitation, and `GET /visitors/{visitorId}/timeline` only when showing a group co-visitor's visit. Individual invitations (primary contact has no visitor id) SHALL always use the invitation endpoint.

#### Scenario: Invitation timeline
- **WHEN** the detail of an invitation is opened
- **THEN** the invitation endpoint is called with the invitation id

#### Scenario: Co-visitor timeline
- **WHEN** a group co-visitor's timeline is requested by visitor id
- **THEN** the visitor endpoint is called

### Requirement: Events are paged, sorted and filtered server-side
The timeline SHALL send optional `page`, `pageSize` (default 20, max 100), `occurredAfter`/`occurredBefore` (ISO datetimes, inclusive), `sortBy` (`occurred_at` | `event_type`) and `sortOrder` (`desc` | `asc`). The default is newest first.

#### Scenario: Default view
- **WHEN** the timeline first loads
- **THEN** events appear newest first, 20 per page

#### Scenario: More pages
- **WHEN** `pagination.totalPages` exceeds the current page
- **THEN** the user can load the next page

### Requirement: Each event is rendered from its display fields
Each event SHALL show a label and icon for its `eventType`, the `summary` verbatim, `occurredAt` formatted as a date-time, and `actorName` when non-null. Known types: `invited`, `approved`, `denied`, `approval_reverted`, `id_verified`, `photo_captured`, `checked_in`, `checked_out`, `badge_printed`, `badge_reprinted`, `notification_sent`.

#### Scenario: Actor present
- **WHEN** an event has `actorName` "Asha Rao"
- **THEN** the row shows that name as the actor

#### Scenario: System or visitor action
- **WHEN** `actorName` is `null` (e.g. QR check-in, auto check-out)
- **THEN** no actor is shown and no placeholder name is invented

#### Scenario: Unknown event type
- **WHEN** an event has an `eventType` the client does not know
- **THEN** it renders as a generic event with its `summary`, and the page does not fail schema validation

#### Scenario: Summary is not parsed
- **WHEN** a summary contains masked contact details
- **THEN** it is displayed as received

### Requirement: Empty and error states
An empty list SHALL show an empty state, not an error. Failures SHALL be reported without crashing the modal.

#### Scenario: No events
- **WHEN** the API returns `data: []`
- **THEN** an empty state such as "No timeline events recorded" is shown

#### Scenario: 404, 403 or 422
- **WHEN** the API returns 404, 403 or 422
- **THEN** the error message from the standard envelope is shown in the timeline section only, with a retry action

### Requirement: Out-of-scope events are not built
The timeline SHALL NOT include zone or overstay UI, SHALL NOT redact fields client-side, and SHALL NOT be gated by a feature flag.

#### Scenario: Unrecognised zone event
- **WHEN** a future zone event type arrives
- **THEN** it renders as a generic event
