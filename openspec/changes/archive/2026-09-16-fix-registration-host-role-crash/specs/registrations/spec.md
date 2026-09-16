## ADDED Requirements

### Requirement: Walk-in Registration Enforces the Server-Resolved Branch's Form-Builder Configuration
A walk-in registration's required fields, allowed custom-field keys/options,
and consent keys SHALL be validated against the published form-builder
configuration of the branch the server itself resolves (via device
credential, or the default-tenant/default-branch fallback) — never against
a branch a client may have separately assumed or rendered. WHEN a submitted
registration is rejected because it does not match the server-resolved
branch's configuration, the system SHALL log which branch was enforced, so
a client/server branch divergence is distinguishable in the log from any
other validation failure.

#### Scenario: Submission is validated against the server-resolved branch, not a client-assumed one
- **WHEN** a walk-in registration is submitted, and the server resolves a
  branch (by device credential or default-tenant/default-branch fallback)
- **THEN** the submission's required fields, custom-field keys/options, and
  consent keys are validated against that resolved branch's published
  form-builder configuration, regardless of which branch's configuration
  the submitting client fetched or rendered

#### Scenario: A configuration mismatch is logged with the enforced branch
- **WHEN** a walk-in registration is rejected for a required-field, custom-
  field, or consent-key mismatch against the server-resolved branch's
  configuration
- **THEN** the rejection is logged with the resolved branch's id, so an
  operator can tell from the log whether the submitting client was
  rendering a different branch's configuration
