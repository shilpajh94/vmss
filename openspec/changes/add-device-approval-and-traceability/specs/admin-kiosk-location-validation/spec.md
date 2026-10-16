## Purpose

The admin-kiosk-location-validation capability lets an admin control whether kiosk check-ins must match the device's registered branch and building.

## ADDED Requirements

### Requirement: Setting is loaded and displayed
The system SHALL read the kiosk location validation setting and show its current state as a toggle, treating the backend default of enabled as authoritative, for users with `settings:view`.

#### Scenario: Setting loads
- **WHEN** a user with `settings:view` opens the setting
- **THEN** the toggle reflects `enforceKioskLocationValidation` from the server

#### Scenario: Load failure
- **WHEN** the read fails
- **THEN** the system shows an error and allows retry

### Requirement: Setting can be changed
The system SHALL send the new `enforceKioskLocationValidation` boolean to the server when an admin with `settings:manage` toggles it, and SHALL show the server-confirmed value on success and revert the toggle with an error on failure.

#### Scenario: Disable validation
- **WHEN** an admin with `settings:manage` turns the toggle off
- **THEN** the system saves `false` and shows a success notification

#### Scenario: Save fails
- **WHEN** the save fails
- **THEN** the toggle returns to its previous value and an error is shown

### Requirement: Setting is permission-gated
The system SHALL render the toggle read-only for users with `settings:view` but without `settings:manage`, and SHALL NOT show it to users without `settings:view`.

#### Scenario: View-only user
- **WHEN** a user has `settings:view` only
- **THEN** the toggle is visible but cannot be changed
