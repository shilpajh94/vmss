## ADDED Requirements

### Requirement: Company and Tenant Timezones Resolve Consistently, Including Legacy Offset Values
Every place that turns the stored company or tenant timezone into a clock
SHALL use one resolution rule: expiry, visit-time display, dashboards,
calendar and exports. The rule SHALL accept an IANA zone name (e.g.
`Asia/Kolkata`). It SHALL also accept the legacy UTC-offset form already
stored by the web (`GMT+05:30`, `UTC-04:00`) as the equivalent fixed
offset. Only a value that is neither SHALL fall back to the tenant default
and then UTC, and the fallback SHALL be logged at WARNING once per value.
Writes SHALL continue to accept the same values they accept today.

#### Scenario: Legacy offset value no longer falls back to UTC
- **WHEN** a company's stored timezone is `GMT+05:30` and an invitation's
  expiry is computed
- **THEN** the expiry is computed at UTC+05:30, not UTC

#### Scenario: IANA name is honoured
- **WHEN** a company's stored timezone is `Asia/Kolkata`
- **THEN** dashboards, calendar, exports and expiry all use that zone

#### Scenario: Unrecognised value is logged
- **WHEN** a stored timezone is neither an IANA name nor a UTC-offset form
- **THEN** resolution falls back to the tenant default, then UTC, and a
  WARNING naming the tenant and the value is logged
