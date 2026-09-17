## ADDED Requirements

### Requirement: Unresolvable Default Host Role Fails the Submission as a Server Misconfiguration
WHEN an invitation is submitted (not auto-approved) and the tenant's default
host role cannot be resolved (no `Company.default_host_role_id` override
resolves to an existing role, and the tenant's standard `reception` role
also does not exist), the system SHALL reject the submission with 500,
log the failure at `ERROR` (per `logging-observability.md` §3), and SHALL
NOT persist the invitation, its visitors/vehicles, or any approval step —
this is a tenant-provisioning gap, not a validation failure the caller can
correct by resubmitting.

#### Scenario: Missing default host role rejects the submission
- **WHEN** an invitation is submitted for a tenant whose standard
  `reception` role does not exist and whose `Company.default_host_role_id`
  is unset or points at a deleted role
- **THEN** the request is rejected with 500 and no `Invitation` row (or any
  of its visitors, vehicles, or approval steps) exists afterward

#### Scenario: Failure is traceable to the affected tenant
- **WHEN** the default-host-role resolution failure above occurs
- **THEN** the `ERROR` log line carries the request's `tenant_id` (bound
  automatically per `logging-observability.md` §1), so the affected tenant
  is identifiable from the log alone
