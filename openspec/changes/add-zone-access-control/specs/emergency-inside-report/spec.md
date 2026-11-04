## ADDED Requirements

### Requirement: Who's Inside by Zone
The system SHALL expose `GET /api/v1/emergency/inside`, requiring `emergency:view`, listing for each zone the visits currently inside, plus an `unzoned` bucket of checked-in visits currently inside no zone.

#### Scenario: Occupancy
- **WHEN** a visit's latest allowed event for a zone is `entry` and the visit is still checked in
- **THEN** it is listed under that zone

#### Scenario: Exited or checked out
- **WHEN** the latest event is `exit`, or the visit is checked out
- **THEN** it is not listed as inside

#### Scenario: Denied entry is not occupancy
- **WHEN** an entry was denied
- **THEN** the visit is not listed in that zone

#### Scenario: Unzoned
- **WHEN** a checked-in visit has never scanned in, or has exited every zone
- **THEN** it appears in the `unzoned` bucket

#### Scenario: Branch scope and PII
- **WHEN** a caller requests the report
- **THEN** only branches the caller may see are included, and entries carry name, host and badge number only

#### Scenario: Constant query count
- **WHEN** the report is built for 5 or 500 occupants
- **THEN** the number of queries is the same

#### Scenario: Permission and flag
- **WHEN** the caller lacks `emergency:view` the response is 403; when the tenant's toggle is off it is 404

### Requirement: Zone Events in the Visit Timeline
The system SHALL include `zone_entered`, `zone_exited` and `zone_entry_denied` events in the visit timeline, sourced from the zone access log.

#### Scenario: Timeline shows zone events
- **WHEN** a visit has zone scans
- **THEN** its timeline lists them in time order with the zone name and, for denials, the reason code

#### Scenario: Toggle off
- **WHEN** the tenant's toggle is off
- **THEN** no zone events appear
