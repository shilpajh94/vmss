## ADDED Requirements

### Requirement: Branch Deletion Is Blocked While Actively Referenced
Soft-deleting a `Branch` SHALL be rejected with 409, leaving the branch
undeleted, while it still has any active (non-soft-deleted) `Building`,
`Floor`, `Department`, `ReceptionDesk`, or `SecurityGate` row, or any active
`RegistrationDeviceKey` provisioned against it — the same referential-
integrity posture the system already applies to deleting a `Role` with
active `UserBranchRole` grants. A `Branch` with no such active references
SHALL soft-delete normally.

#### Scenario: Deleting a branch with an active child is rejected
- **WHEN** a caller with `branches:manage` attempts to delete a `Branch`
  that still has at least one non-soft-deleted `Building`, `Floor`,
  `Department`, `ReceptionDesk`, or `SecurityGate`
- **THEN** the request is rejected with 409 and the branch is left
  undeleted

#### Scenario: Deleting a branch with an active device credential is rejected
- **WHEN** a caller with `branches:manage` attempts to delete a `Branch`
  that a non-deactivated `RegistrationDeviceKey` is still provisioned
  against
- **THEN** the request is rejected with 409 and the branch is left
  undeleted, so a kiosk's device credential can never silently start
  failing because the branch it authenticates against disappeared out from
  under it

#### Scenario: A branch with no active references can be deleted
- **WHEN** a caller with `branches:manage` deletes a `Branch` that has no
  active child Building/Floor/Department/ReceptionDesk/SecurityGate and no
  active `RegistrationDeviceKey` referencing it
- **THEN** the branch is soft-deleted normally

### Requirement: Child Entities Cannot Be Created Under an Already Soft-Deleted Parent
Creating a `Building` or `Department` under a `Branch`, a `Floor` under a
`Building`, or a `ReceptionDesk`/`SecurityGate` under a `Floor`/`Branch`
SHALL be rejected with 404 when the named parent has been soft-deleted —
the same 404 already returned for a parent id that never existed, since a
soft-deleted row is invisible to normal lookups either way.

#### Scenario: Creating a building under a soft-deleted branch is rejected
- **WHEN** a caller with `buildings:manage` submits `POST /buildings` with a
  `branchId` that belongs to a soft-deleted `Branch`
- **THEN** the request is rejected with 404 and no building is created

#### Scenario: Creating a floor under a soft-deleted building is rejected
- **WHEN** a caller with `floors:manage` submits `POST /floors` with a
  `buildingId` that belongs to a soft-deleted `Building`
- **THEN** the request is rejected with 404 and no floor is created

#### Scenario: Creating a department under a soft-deleted branch is rejected
- **WHEN** a caller with `departments:manage` submits `POST /departments`
  with a `branchId` that belongs to a soft-deleted `Branch`
- **THEN** the request is rejected with 404 and no department is created

#### Scenario: Creating a reception desk under a soft-deleted floor is rejected
- **WHEN** a caller with `desks:manage` submits `POST /reception-desks` with
  a `floorId` that belongs to a soft-deleted `Floor`
- **THEN** the request is rejected with 404 and no reception desk is
  created

#### Scenario: Creating a security gate under a soft-deleted branch is rejected
- **WHEN** a caller with `gates:manage` submits `POST /security-gates` with
  a `branchId` that belongs to a soft-deleted `Branch`
- **THEN** the request is rejected with 404 and no security gate is created
