## Context

- `ZoneSetSection` + `useZoneSet` own load/save for an existing category or invitation. For a category they list all zones across branches and read/PUT the saved set by category id, so they cannot run before the category exists.
- `ZonePicker` is a pure checkbox list (`zones`, `selectedIds`, `onToggle`, `mode`, `branchNames`) and is reusable as is.
- `ZoneFeatureContext.enabled` is true only after `GET /zones` succeeds and the user has `zones:view`; `ZoneSetSection` already returns null when it is false.
- `listZonesUseCase` already accepts `isDefault` (added by `add-default-zone-support`), and `setCategoryZonesUseCase` already does the PUT.
- A category spans branches, but the default is per branch. `GET /zones` is scoped to the current branch (X-Branch-ID), so the pre-selected zone is the current branch's default.

## Decisions

1. **Create-mode checklist is local state, saved after create.** Keep a `zoneDraft: string[]` in `useAdminVisitorCategoryForm` (create mode only). Edit mode keeps using `ZoneSetSection` unchanged. Rejected: creating the category first and then redirecting to edit to pick zones, which does not give "checked by default".
2. **Zone list for the picker.** On create, load active zones with `fetchAllPages(listZonesUseCase.execute(...))` as `useZoneSet` does, plus the default via `listZonesUseCase.execute({ isDefault: true, isActive: true, pageSize: 1 })`. Take the first result only (at most one default per branch) and seed `zoneDraft` with its id; empty list seeds `[]`. Seed once on load, never again, so an admin's unticking is not overwritten by a re-render or retry of an unrelated field.
3. **Gating.** Render the create checklist only when `useZoneFeature().enabled`. Users without `zones:manage` see no editable checklist and no PUT is made (they could not make it); the default is not fetched for them either, as the checklist is hidden. `canManageZones` is already read in the form page.
4. **Component placement.** Add a small presentational `ZoneDraftSection` (in `presentation/components/zones/`) wrapping `ZonePicker` with the title and help text, used by the create form. Do not stretch `ZoneSetSection` to cover a not-yet-existing id. The data loading lives in the form hook, since the hook already orchestrates the create flow.
5. **Save sequence.** After `createVisitorCategoryUseCase.execute`, and before or alongside the existing best-effort Reception workflow step, run `setCategoryZonesUseCase.execute(created.id, zoneDraft)` when `zoneDraft.length > 0` and the user can manage zones. Wrap it in its own try/catch: on failure the category stays created, a toast explains "Category created, but zones could not be saved. Set them from the Edit page.", and navigation goes to `/admin/visitor-categories/{id}/edit` (existing edit route; confirm its path when applying) so the admin can retry. Success keeps the current toast and navigation.
6. **Failed default lookup is non-blocking.** If the default fetch fails (not 404), show the checklist unticked and do not block the form. A 404 means the zone feature is off: call `reportDisabled()` as other zone pages do.
7. **Inactive and stale zones.** Only active zones are offered on create, so no inactive zone can be newly picked, which matches `ZonePicker`'s existing behaviour.

## Risks / Trade-offs

- **Partial failure**: category created but zone PUT fails; mitigated by decision 5.
- **Multi-branch category vs one-branch default**: pre-selecting only the current branch's default is what was asked; the admin can tick other branches' zones.
- **Duplicated list-loading logic** between the create hook and `useZoneSet`; accepted, small, and avoids coupling create state to an id.

## Open Questions

- Confirm the checklist on create is wanted as a new section (assumed yes; see proposal).
