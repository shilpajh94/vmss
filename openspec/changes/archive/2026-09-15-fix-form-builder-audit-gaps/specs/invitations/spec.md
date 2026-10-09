## MODIFIED Requirements

### Requirement: Consent Is Mandatory and Recorded
An invitation SHALL be created only if the primary contact has accepted
every required consent (terms and conditions, data processing, and safety
guidelines). The system SHALL record what was consented to and when. The
consent payload SHALL be bounded to the branch's configured set of consent
keys — a request MAY omit a non-required key but SHALL NOT introduce any key
outside that configured set, and the number of keys accepted SHALL be capped
to the size of the branch's configured consent set.

#### Scenario: Missing consent rejected
- **WHEN** a creation request has any required consent flag set to false or
  omitted
- **THEN** the system rejects the request and creates no invitation record

#### Scenario: Full consent accepted and timestamped
- **WHEN** a creation request has every required consent flag set to true
- **THEN** the system stores the acceptance along with the timestamp it was
  recorded

#### Scenario: Unknown consent key rejected
- **WHEN** a creation request's consent payload includes a key that is not
  in the branch's configured consent set
- **THEN** the system rejects the request and creates no invitation record

#### Scenario: Oversized consent payload rejected
- **WHEN** a creation request's consent payload contains more keys than the
  branch's configured consent set defines
- **THEN** the system rejects the request and creates no invitation record
