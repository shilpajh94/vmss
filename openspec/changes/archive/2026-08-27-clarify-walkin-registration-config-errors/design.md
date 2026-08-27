## Context

`_resolve_default_device_context` in `registrations/deps.py` checks the
default tenant then the default branch, each with a single `is None or not
X.is_active` condition, and both failure branches call the shared
`_reject_unconfigured_default(event, **fields)` helper, which logs at
`ERROR` and raises the 401. See proposal.md - Why.

## Goals / Non-Goals

**Goals:**
- Make the not-found-vs-inactive distinction visible in the `ERROR` log
  fields for both the default-tenant and default-branch checks.

**Non-Goals:**
- No change to the 401 response body/status/headers.
- No change to the invalid-device-credential (`WARNING`) path.
- No new settings, no schema/migration change.

## Decisions

- Add a `reason: Literal["not_found", "inactive"]` keyword to
  `_reject_unconfigured_default`, passed through as a structured log field
  rather than folded into the event name (e.g. no
  `registration_default_tenant_not_found` vs. `..._inactive` event-name
  split). Rationale: keeps the two existing event names
  (`registration_default_tenant_unconfigured`,
  `registration_default_branch_unconfigured`) stable for anyone already
  filtering/alerting on them, while still making the cause queryable/
  filterable as a field — consistent with `logging-observability.md` §2's
  structured-fields convention.
- At each call site, split the existing combined condition
  (`tenant is None or not tenant.is_active`) into two branches so the
  correct `reason` can be passed — no behavioral change to *which* requests
  get rejected, only to what's logged.

## Risks / Trade-offs

- [Log volume/shape change could affect an existing alert query keyed on
  the log message text] → Event names are unchanged; only a new field is
  added, so existing name-based alerts keep matching. Anyone parsing the
  message string itself (not the structured field) should switch to the new
  `reason` field, but nothing breaks either way.
