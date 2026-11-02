## ADDED Requirements

### Requirement: Form-Builder, Profile, and Platform Mutations Are Audited
Every successful create, update, delete and reorder of a form-builder step,
group or field SHALL write an audit-log entry, as publish does today. So
SHALL a staff user's own avatar upload. Each entry SHALL name the actor,
action, entity type and entity id, and SHALL be written off the request
path. Superadmin login (success and failure) and tenant provisioning SHALL
write a platform-level audit event to the global schema.

#### Scenario: Field update is audited
- **WHEN** a caller with form-builder management permission updates a
  field's label
- **THEN** an audit entry for that field's update, naming the caller, is
  recorded

#### Scenario: Step reorder is audited
- **WHEN** a caller reorders a form's steps
- **THEN** one audit entry for the reorder is recorded

#### Scenario: Avatar upload is audited
- **WHEN** a staff user uploads their own profile picture
- **THEN** an audit entry naming that user and the user entity is recorded

#### Scenario: Tenant provisioning is recorded at platform level
- **WHEN** a superadmin provisions a new tenant
- **THEN** a platform audit event naming the superadmin and the new tenant
  is recorded in the global schema
