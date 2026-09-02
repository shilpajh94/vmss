## 1. Remove the badge-expiry control from the UI

- [x] 1.1 In `src/presentation/pages/admin-organisation-configs/Components/VisitorPolicyCard.tsx`, remove the "Pass Badge Expiry Duration" label and select control, and drop the `onBadgeExpiryChange` prop from the component's props type and body.
- [x] 1.2 In `src/presentation/pages/admin-organisation-configs/admin-organisation-configs.tsx`, stop passing `onBadgeExpiryChange`/the badge-expiry value into `<VisitorPolicyCard>`.

## 2. Leave the data layer untouched

- [x] 2.1 Confirm `src/domain/entities/organisation-config-schema.ts`, `src/data/use-cases/get-organisation-config.ts`, `src/data/use-cases/update-organisation-config.ts`, and `src/infrastructure/organisation-config-repository.ts` are left as-is — `passBadgeExpiryDuration` keeps round-tripping through `form` state via `save()` unchanged (see design.md).

## 3. Verify

- [ ] 3.1 Load `/admin/organisation-configs`, confirm the Visitor Policy & Security card shows only the "Auto-approve pre-registered visitors" toggle.
- [ ] 3.2 Edit the auto-approve toggle and click "Save Configs"; confirm the save succeeds and the toast fires, with no console/network errors related to the removed field.
