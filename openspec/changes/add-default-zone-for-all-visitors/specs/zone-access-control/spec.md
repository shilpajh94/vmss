## ADDED Requirements

### Requirement: Default Zone
The system SHALL let holders of `zones:manage` mark at most one live, active zone per branch as that branch's default zone, and SHALL treat the default zone as allowed for every visit at that branch regardless of per-invitation or visitor-category zone assignment.

#### Scenario: Visitor with no assigned zones can enter the default zone
- **WHEN** a visit has no invitation zones and its category has no defaults, and the branch has an active default zone linked to the scanning gate
- **THEN** `can_enter` allows the entry to the default zone and denies every other zone with `zone_not_allowed`

#### Scenario: Explicit assignment does not remove the default zone
- **WHEN** reception assigned zones A and B to a visit and the branch default zone is D
- **THEN** the effective allowed set is {A, B, D}

#### Scenario: Other checks still apply
- **WHEN** a visit is not approved, is blacklisted, is outside its time window, or the gate is not linked to the default zone
- **THEN** entry to the default zone is denied with the usual reason (`not_approved`, `blacklisted`, `outside_time_window`, `gate_not_linked`)

#### Scenario: Front-desk check-in uses it too
- **WHEN** the check-in device is linked to exactly one zone, that zone is the branch default, and the visit has no zone assignment
- **THEN** the check-in is allowed and an `entry` event is logged

#### Scenario: No default configured
- **WHEN** the branch has no default zone and the visit has no assigned zones
- **THEN** behavior is unchanged: every zone is denied with `zone_not_allowed`

#### Scenario: Other branch's default does not apply
- **WHEN** a visit belongs to branch X and the default zone belongs to branch Y
- **THEN** the default zone is not in the visit's allowed set

### Requirement: Setting the Default Zone
The system SHALL accept `isDefault` on zone create and update, keep one default per branch, and return `isDefault` on every zone response.

#### Scenario: Set a default
- **WHEN** a caller with `zones:manage` sets `isDefault: true` on an active zone
- **THEN** the zone becomes the branch default, the previous default (if any) is cleared in the same transaction, and one audit entry records the old and new default ids

#### Scenario: Clear the default
- **WHEN** a caller sends `isDefault: false` for the current default zone
- **THEN** the branch has no default zone

#### Scenario: Inactive or deleted zone cannot be default
- **WHEN** `isDefault: true` is sent for an inactive or soft-deleted zone
- **THEN** the response is 422 (404 for a deleted zone)

#### Scenario: Default zone is protected
- **WHEN** a caller deletes or deactivates the current default zone
- **THEN** the response is 409 and nothing changes

#### Scenario: Database guarantees one per branch
- **WHEN** two live zones in the same branch are both written with `is_default = true`
- **THEN** the partial unique index rejects the second write

#### Scenario: Permission and toggle
- **WHEN** the caller lacks `zones:manage`, or the tenant toggle is off
- **THEN** the response is 403 and 404 respectively, as for every zone write

#### Scenario: Listing filter
- **WHEN** the zone list is requested with `isDefault=true`
- **THEN** only default zones are returned
