## Context

See proposal.md - Why. Relevant current-state facts from the frontend code
(`VMMS_WEB`):

- `VehicleInfoStep.tsx` already receives a `customFields: FormField[]` prop
  (the active Vehicle Info custom fields for the resolved branch) and
  already uses it to render `<CustomFieldsSection>` in the "Add New
  Vehicle" form. It is not used anywhere in the vehicle list `<table>`.
- `ReviewConfirmStep.tsx` is a presentational component driven by a
  `ReviewableFormState` prop. It has **no** `FormField[]` metadata for any
  step today — it only knows raw `formState.vehicles`/`carriedItems`, and
  builds each summary row by hand from fixed keys. It also has no access to
  `formState.customFieldValues` (the flat bucket Carried Items' custom
  fields live in — see `types.ts`'s `CustomFieldValues` comment).
- Both `visitor-request.tsx` (public wizard) and
  `staff-visitor-registration.tsx` (staff wizard), plus their respective
  `use-*-wizard.ts` hooks, instantiate `ReviewConfirmStep` and already have
  the resolved Vehicle Info / Carried Items `FormField[]` lists in scope
  (they're what's passed into `VehicleInfoStep`/`CarriedItemsStep` today).
- There is no existing "format a `DynamicFieldValue` for read-only display"
  helper. `DynamicField.tsx` only renders editable inputs; `prettifyKey`
  formats a raw key/option string into a label, nothing formats a *value*
  (e.g. a `boolean` or `string[]`).

## Goals / Non-Goals

**Goals:**
- Vehicle Info's vehicle list table and Review & Confirm's Vehicle
  Info/Carried Items summaries render every active custom field's value.
- One shared, small value-formatting helper, not two divergent
  implementations in the table and the summary.

**Non-Goals:**
- No change to `file_upload`/`dynamic_table`/`signature_pad`/
  `rich_text_block` inline-rendering limitations already called out in
  `DynamicField.tsx` — those field types aren't in scope for Vehicle Info
  or Carried Items today, and adding read-only rendering for them is
  deferred to whenever they're actually wired up for input.
- No change to which fields are "fully configurable" or how fields are
  authored/published (form-builder admin side) — display-only.
- No change to what a *removed or renamed* custom field's already-submitted
  historical values look like on an already-submitted invitation's detail
  view (staff-facing invitation detail screens, if any, are a separate
  surface from this wizard and out of scope).

## Decisions

**1. Which fields determine the table's columns / the summary's rows: the
current step config, not the union of keys present in submitted data.**
Use the `customFields: FormField[]` prop already passed into
`VehicleInfoStep` (active fields for the currently-resolved branch
config) as the source of truth for both the table's extra columns and the
Review & Confirm rows — not a scan of whatever keys happen to be present
across `vehicle.customFieldValues`. Rationale: the same list the "Add New
Vehicle" form already uses to decide which inputs to render; keeping one
source of truth means a field that's active when the vehicle is added is
guaranteed to have a matching column immediately, with no separate sync
step. This is a single-session wizard (not editing a previously-submitted,
possibly-stale invitation), so "config changed since this vehicle was
added" isn't a real scenario within one wizard session.

**2. Add a shared `formatDynamicFieldValue(field, value): string` helper**
in `components/dynamic-fields/` (alongside `DynamicField.tsx`), covering
the same `DynamicFieldValue` union (`string | boolean | string[] |
undefined`): boolean → "Yes"/"No", `string[]` → comma-joined
`prettifyKey`-formatted values, `string` → the value itself (or
`prettifyKey` for an `options`-bearing field, matching how the edit-mode
checkbox list already labels options), `undefined`/`''`/`[]` → `'—'`. Both
`VehicleInfoStep`'s table and `ReviewConfirmStep`'s summaries call this
one helper. Rationale: avoids the table and the summary silently drifting
into two different renderings of the same boolean/array value.

**3. Thread `FormField[]` into `ReviewConfirmStep` as two new optional
props: `vehicleCustomFields` and `carriedItemsCustomFields`**, both
defaulting to `[]` when absent. `ReviewableFormState` gains a
`customFieldValues: CustomFieldValues` field (mirroring
`VisitRequestFormState`) so the Carried Items summary can look up values
from the shared flat bucket the same way `CarriedItemsStep` already does.
Rationale: keeps `ReviewConfirmStep` a pure presentational component (props
in, JSX out) rather than reaching into a wizard hook itself; the two call
sites (`visitor-request.tsx`, `staff-visitor-registration.tsx`) already
have both field lists and `formState.customFieldValues` in scope, so this
is a threading change, not a new data-fetch.

**4. Vehicle table column set is the union across the step's active fields,
not per-row.** All rows in the table share the same column set (the active
`customFields` list); a row missing a value for a given field renders `'—'`
in that cell via decision 2's helper, rather than the table growing/
shrinking columns per vehicle. This matches how the fixed columns
(Make/Model, Color) already behave when those fields are inactive for the
branch (the column isn't there at all) versus present-but-empty (shown as
blank) — active-but-unanswered custom fields render as `'—'`, distinct
from "this field isn't configured for this branch" (column absent
entirely).

## Risks / Trade-offs

- **[Risk]** Widening the vehicle table with several custom columns could
  crowd small screens. → **Mitigation**: the table container already has
  `overflow-x-auto` (`VehicleInfoStep.tsx`), so extra columns scroll
  horizontally rather than breaking layout; no new responsive handling
  needed.
- **[Risk]** Prop-threading `vehicleCustomFields`/`carriedItemsCustomFields`
  touches both wizard pages and both hooks (4 files), slightly more surface
  than a single-component fix. → **Mitigation**: each is a narrow,
  mechanical pass-through of data the hook already computes for the
  corresponding step component; no new state or fetching logic.

## Migration Plan

Frontend-only, additive rendering change behind no flag. Ship as a normal
deploy; no data migration, no backend deploy coordination required (backend
already returns/persists everything needed).
