## REMOVED Requirements

### Requirement: Visitor Policy & Security section captures auto-approve and badge expiry
**Reason**: The badge-expiry control is being removed from the Organisation Configs page per stakeholder request; auto-approve remains and is covered by the new "Visitor Policy & Security section captures auto-approve setting" requirement below.
**Migration**: No admin-facing migration — the badge-expiry value is no longer editable from this page, but nothing about the stored value changes (see design.md).

## ADDED Requirements

### Requirement: Visitor Policy & Security section captures auto-approve setting
The system SHALL let an admin toggle "Auto-approve pre-registered visitors" on or off. The system SHALL NOT display a pass badge expiry duration control in this section.

#### Scenario: Admin toggles auto-approve
- **WHEN** an admin activates the "Auto-approve pre-registered visitors" toggle
- **THEN** the toggle reflects the new on/off state as unsaved

#### Scenario: No badge expiry control shown
- **WHEN** the Organisation Configs page loads
- **THEN** the Visitor Policy & Security section does not show a "Pass Badge Expiry Duration" field

## MODIFIED Requirements

### Requirement: Organisation configuration loads on page entry
The system SHALL, when the Organisation Configs page loads, fetch the current organisation configuration — organisation name, logo, default timezone, and auto-approve setting — and populate the form with the retrieved values.

#### Scenario: Configuration loads successfully
- **WHEN** the Organisation Configs page loads and the fetch succeeds
- **THEN** the General Information and Visitor Policy & Security fields are populated with the retrieved organisation configuration

### Requirement: Save Configs persists the edited configuration
The system SHALL, when "Save Configs" is activated, submit the current form values to persist the organisation configuration, and SHALL trigger a success notification when the save succeeds.

#### Scenario: Save succeeds
- **WHEN** an admin activates "Save Configs" and the update succeeds
- **THEN** the system persists the edited organisation name, logo, default timezone, and auto-approve setting, and triggers a success notification
