## Why

The visitor request form and the staff Register Visitor form show "Step
0 of 0" and "Something went wrong loading the registration form" for
every branch that uses the tenant-default form.

`GET /form-builder/effective` returns a published snapshot from 22 Sep
2026. Parsing it with `EffectiveFormStepListResponseSchema` fails with 31
issues:
- 27 fields have no `hideLabel`, because the key was added after publish;
- 3 groups have no `visibilityCondition`, for the same reason;
- 1 field is of type `signature_pad`, which has since been removed.

The zod schema is strict and all-or-nothing, so one outdated key or one
unknown field discards the entire form. The newer branch-scoped snapshot
parses fine.

The API fix (`heal-stale-form-config-data` in VMSS_API) serves snapshots
in the current shape and migrates the data. This change makes the client
degrade gracefully as well. A deploy where the web app is newer than the
API, or an older API still serving an old snapshot, should never blank the
whole form again.

## What Changes

- Form-builder parsing tolerates older and unknown data:
  - a field's `hideLabel` defaults to `false` when absent;
  - a group's `visibilityCondition` defaults to `null` when absent;
  - a field whose `fieldType` isn't a supported type is dropped from its
    step (with a `console.warn` naming its key and type), instead of
    failing the whole response.

  This applies to the effective form (the visitor request and staff
  registration pages) and to the admin Form Builder reads, which share
  the field schema.
- A dropped field never appears in the wizard, never counts toward
  "Step N of M", and is never submitted.
- No UI change otherwise.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `visitor-request-wizard`: adds the requirement that the wizard still
  renders when the published configuration is older than the client or
  contains an unknown field type.
- `staff-visitor-registration`: the same requirement for the staff Register
  Visitor form.

## Impact

- `src/domain/entities/form-builder-schema.ts`: `hideLabel` and group
  `visibilityCondition` defaults, and a tolerant field-list schema that
  filters unsupported types.
- New `scripts/check-effective-form.ts` verification, run with
  `npx tsx`: it parses a saved or live effective-form response.
- There's no new dependency.
