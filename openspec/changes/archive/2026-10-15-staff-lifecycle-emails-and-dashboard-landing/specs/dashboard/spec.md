## ADDED Requirements

### Requirement: Personal Dashboard Overview Scoped to the Caller's Relevant Invitations
The system SHALL provide `GET /admin/dashboard/my-overview` to any
authenticated user of the tenant. No branch-level permission is required,
the same gate as `GET /invitations?relevantToMe=true`. It returns counts
and a preview computed **only** over the invitations relevant to the
caller. That is exactly the set `GET /invitations?relevantToMe=true` would
return for the same caller at the same moment. It SHALL ignore
`X-Branch-ID` and SHALL NOT accept a `branchId` parameter. The response
SHALL contain:

- `visitsToday`: relevant invitations whose scheduled visit date is today
  and whose status is `approved`, `checked_in` or `checked_out`;
- `insideNow`: relevant invitations currently `checked_in`;
- `awaitingApproval`: relevant invitations in status `submitted`;
- `upcoming`: relevant invitations in status `approved` that have never
  been checked in and have not expired;
- `upcomingPreview`: up to 5 of those upcoming invitations, soonest
  scheduled visit first. Each row carries `trackingId`, the visitor's name,
  scheduled date and time, and purpose.

"Today" SHALL be evaluated in the tenant's configured timezone, the same as
the branch-wide overview. `archived` and `denied` invitations SHALL count
toward none of the figures. The response SHALL be read-only and SHALL NOT
reveal any invitation outside the caller's relevant set.

#### Scenario: A host sees only their own visits
- **WHEN** host H, who holds only the `host` role, requests
  `my-overview` at a branch with 10 invitations, 3 of which name H as
  resolved host
- **THEN** every count and the preview reflect only those 3 invitations,
  and the request succeeds with 200

#### Scenario: Counts agree with the relevantToMe list
- **WHEN** a caller requests `my-overview` and then
  `GET /invitations?relevantToMe=true&status=submitted`
- **THEN** `awaitingApproval` equals that list's total

#### Scenario: Archived and denied visits are excluded
- **WHEN** a caller's relevant set contains one `archived` and one
  `denied` invitation, both scheduled for today
- **THEN** neither is counted in `visitsToday`, `upcoming` or any other
  figure

#### Scenario: Unauthenticated request is rejected
- **WHEN** `my-overview` is requested without a valid access token
- **THEN** the system returns 401 and no data

#### Scenario: Branch header does not widen the scope
- **WHEN** a host sends `my-overview` with `X-Branch-ID` set to a branch
  where they hold no role
- **THEN** the response still reflects only the host's own relevant
  invitations

#### Scenario: Preview is bounded and ordered
- **WHEN** a caller has 8 upcoming relevant invitations
- **THEN** `upcoming` is 8 and `upcomingPreview` lists the 5 with the
  soonest scheduled visit, soonest first
