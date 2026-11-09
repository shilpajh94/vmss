## ADDED Requirements

### Requirement: Repeat Check-In Re-Evaluates Current Zone Access

When the tenant's zone access is enabled and a check-in is made from a security device linked to exactly one zone, a check-in call on a visit that is already `checked_in` SHALL judge that zone against the visit's current allowed zones. This applies to the QR-token and check-in-code check-in endpoints. It SHALL NOT return a pass without a zone decision.

#### Scenario: Zone still allowed on repeat check-in
- **WHEN** a visit is `checked_in`, its allowed zones include the device's zone, and check-in is called again from that device
- **THEN** the response is 200 "Verification passed" with unchanged data
- **AND** `checkedInAt` is not re-stamped, no new `entry` event is written, and no host notification or check-in audit entry is created

#### Scenario: Zone removed after check-in
- **WHEN** a visit is `checked_in`, reception then removes the device's zone from its allowed zones, and check-in is called again from that device
- **THEN** the response is 403 `Zone entry denied` with the stable deny reason
- **AND** a `denied` zone event and audit entry are recorded and Security is alerted
- **AND** the visit remains `checked_in`

#### Scenario: Zone added after check-in
- **WHEN** a visit is `checked_in` without the device's zone, reception adds that zone, and check-in is called again from that device
- **THEN** the response is 200 "Verification passed"

#### Scenario: Check-in after check-out uses current zones
- **WHEN** a visit is checked out, its allowed zones are updated, and it is checked in again from a single-zone device
- **THEN** the zone decision uses the updated allowed zones, as it does today

#### Scenario: Device not tied to one zone
- **WHEN** a repeat check-in comes from no device, a non-security device, or a device linked to zero or several zones
- **THEN** the response is the existing idempotent 200 with no zone decision

#### Scenario: Zone access disabled
- **WHEN** the tenant's `zone_access_enabled` is off
- **THEN** a repeat check-in behaves exactly as before this change
