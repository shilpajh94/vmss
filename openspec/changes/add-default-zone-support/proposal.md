## Why

The backend is adding a **default zone** per branch: one zone that is always allowed for every visitor at that branch, even when reception forgot to assign zones. Until now a visit with no mapped zones was denied everywhere, and the portal warned about it. The portal cannot yet mark a zone as the default, and its "no zones mapped, every zone is denied" warning becomes wrong for any branch that has a default.

The API change is additive (`/api/v1`): a branch with no default behaves exactly as before, and nothing is a default until an admin sets one, so there is no migration. The backend is not yet committed or deployed, so the portal only sees the new field once that branch is merged and deployed; the schema change must tolerate its absence.

## What Changes

- Zone schema gains `isDefault: boolean` (tolerant: defaults to `false` when absent, so the portal works before the backend deploys).
- Zone create/update send an optional `isDefault`. Turning it on for a zone moves the default from the previous zone automatically; turning it off on the current default leaves the branch with none.
- **Zones admin**: a "Default zone" toggle on the zone form, a "Default" badge in the zones table, and a "Default zone" filter (`GET /zones?isDefault=true|false`).
- **Error handling**: deleting or deactivating the current default (409) shows "Choose another default zone first."; making an inactive zone the default (422) shows the backend message; a user without `zones:manage` at the zone's branch gets 403 and sees the normal error message.
- **Invitation/visit zone picker**: show the branch's default zone as a locked, always-selected "Always allowed" chip, found with `GET /zones?isDefault=true`. It is not part of `GET /invitations/{id}/zones` and is never sent in `PUT /invitations/{id}/zones`.
- **Warning logic**: the "every zone will be denied" warning is suppressed (replaced with accurate wording) when the visit's branch has an active default zone.
- Default zone does not bypass approval, blacklist, time-window or gate-link checks. The UI explains that it still needs a linked gate.

Out of scope: guard app scan behaviour (`gate_not_linked`), category default zones (the category picker spans branches and is not a visit), and any data migration.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `admin-zones`: default-zone toggle, badge, filter, and 409/422/403 handling.
- `visit-zone-access`: "Always allowed" default-zone chip in the visit picker and corrected "denied everywhere" warning.

## Impact

- `src/domain/entities/zone-schema.ts` (`isDefault` on `ZoneSchema` and `ZoneInput`).
- `src/data/repositories/zone-repository.ts` (`isDefault` list filter), `src/infrastructure/zone-repository.ts` (pass `isDefault` query param). Use cases pass-through, unchanged.
- `src/presentation/pages/admin-zones/` (form, hooks, table, filter panel, delete/deactivate error handling).
- `src/presentation/components/zones/ZonePicker.tsx`, `ZoneSetSection.tsx`, `src/presentation/hooks/use-zone-set.ts`.
- No new dependencies, no new endpoints, no composition-root changes.
