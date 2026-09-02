## REMOVED Requirements

### Requirement: Assigned receptionist options come from the organisation's existing host employees
**Reason**: "Host employees" is being relabeled to "employees" as part of the admin-wide "Host Employee" → "Employee" rename.
**Migration**: No admin-facing migration — same behavior, relabeled wording.

## ADDED Requirements

### Requirement: Assigned receptionist options come from the organisation's existing employees
The system SHALL populate the Assigned Receptionist field's options from the organisation's existing employees, and SHALL allow the field to be left unassigned.

#### Scenario: Receptionist options loaded
- **WHEN** the Add Reception Desk page loads
- **THEN** the Assigned Receptionist field offers every employee currently in the organisation, plus an option to leave the desk unassigned
