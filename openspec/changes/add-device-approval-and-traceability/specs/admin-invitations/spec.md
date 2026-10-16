## ADDED Requirements

### Requirement: Invitation detail shows check-in and check-out devices
The system SHALL show, in the visitor/invitation detail, the device that performed check-in and the device that performed check-out (name, operating mode, device ID) when `checkInDevice` / `checkOutDevice` are present, and SHALL omit them when null.

#### Scenario: Checked in at a kiosk
- **WHEN** the detail has a `checkInDevice` of mode kiosk
- **THEN** the system shows its name, mode, and device ID alongside the check-in time

#### Scenario: No device recorded
- **WHEN** `checkInDevice` and `checkOutDevice` are null
- **THEN** no device information is shown
