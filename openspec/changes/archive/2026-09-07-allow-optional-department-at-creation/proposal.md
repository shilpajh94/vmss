## Why

The companion `VMMS_WEB` change `role-based-invitation-workflow` (in
progress) removes the "Department to Visit" field from both the visitor
self-service and staff-assisted creation wizards, for the same reason host
was already removed: a visitor rarely knows the receiving organisation's
internal department structure, and staff booking on a visitor's behalf often
guess wrong. Reception is meant to fill it in afterward, once they know the
visitor's actual requirements, via the existing `PATCH /invitations/{id}/edit`
endpoint (which already accepts `departmentToVisit`/`departmentId`). But
`VisitDetailsSubmit.department_to_visit` is currently a required, non-null
`str` field with no default — if the web app stops sending it, invitation and
walk-in creation will fail with a 422 instead of succeeding with the
department left unset, breaking that plan before it ships.

## What Changes

- `department_to_visit` on `VisitDetailsSubmit` (used by both
  `POST /invitations` and `POST /registrations/walk-in`) becomes optional
  (`str | None = None`), matching how `host_name_or_email` is already
  optional on the same schema. Omitting it is now accepted; a submitted
  `departmentId` still resolves and overwrites it exactly as today.
- `Invitation.department_to_visit` (the backing column) becomes nullable,
  since a submitted invitation can now genuinely have no department set at
  creation time.
- Every place that reads `invitation.department_to_visit` and assumes a
  non-null `str` (response schemas, email templates, the approval-email
  visit-detail section) is updated to treat it as optional, rendering
  nothing or a neutral placeholder ("Not yet assigned") rather than an empty
  string or a type error.
- This is purely a relaxation of an existing constraint — a client that
  already always sends `departmentToVisit` sees no behavior change at all.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `invitations`: "Visit Details Optionally Accept Catalog IDs Alongside Free
  Text" — `department_to_visit` changes from a required to an optional
  free-text field, mirroring `host_name_or_email`'s existing optionality.

## Impact

- **Code**: `src/vmss_api/invitations/schemas.py` (`VisitDetailsSubmit`,
  response schemas that surface `departmentToVisit`),
  `src/vmss_api/invitations/models.py` (nullable column + migration),
  `src/vmss_api/core/email_templates/*.html` and
  `src/vmss_api/invitations/tasks.py` (wherever `department_to_visit` is
  interpolated into an email body), `alembic_tenant/versions/` (new
  migration relaxing the `NOT NULL` constraint).
- **API contract**: additive/non-breaking — an existing client that always
  supplies `departmentToVisit` is unaffected; a client that omits it now
  succeeds instead of getting a 422.
- **Companion change**: unblocks `VMMS_WEB`'s `role-based-invitation-workflow`
  change, which depends on this being merged (or at least deployed) before
  its own department-field-removal task can ship without breaking creation.
