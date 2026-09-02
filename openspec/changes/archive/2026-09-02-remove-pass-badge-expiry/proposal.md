## Why

The "Pass Badge Expiry Duration" control on the Organisation Configs page (Visitor Policy & Security section) needs to be removed from the admin UI per stakeholder request — it should no longer be surfaced as an editable setting on this page.

## What Changes

- Remove the "Pass Badge Expiry Duration" field (label + dropdown) from the Visitor Policy & Security card on the Organisation Configs page.
- The "Auto-approve pre-registered visitors" toggle in the same card is unaffected and stays.
- The underlying value keeps round-tripping through the existing `GET`/`PUT` organisation-config calls unchanged (see design.md) — this is a UI-only removal, not a backend contract change, so the admin can no longer view or edit the value from this page, but nothing server-side about the value changes as a result of this proposal.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `admin-organisation-configs`: the Visitor Policy & Security section no longer exposes a badge-expiry control, and the page load/save requirements no longer describe populating or persisting that field from a visible form control.

## Impact

- `src/presentation/pages/admin-organisation-configs/Components/VisitorPolicyCard.tsx` — remove the badge-expiry label/select and its `onBadgeExpiryChange` prop.
- `src/presentation/pages/admin-organisation-configs/admin-organisation-configs.tsx` — stop passing `onBadgeExpiryChange`/badge-expiry value into `VisitorPolicyCard`.
- No change to `src/domain/entities/organisation-config-schema.ts`, the `organisation-config` use cases, or `src/infrastructure/organisation-config-repository.ts` — see design.md for why the field stays in the data layer.
