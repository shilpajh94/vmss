## Why

The icons on the Form Builder's registration-step cards often don't match the step. "Vehicle Info" shows a grid, and "Carried Items" shows a document. The API already stores a correct icon name for each default step (`car`, `briefcase`), but `VMMS_WEB`'s `StepCard.tsx` maps those names to the wrong glyphs. The draggable cards also show a second grid icon as their drag handle, which makes it worse. On top of that, a step created with "Create Registration Step" is never given an icon: the modal sends only a name, the API stores `icon = null`, and every custom step falls back to a generic pencil. Admins can't tell steps apart at a glance.

## What Changes

- **API: pick an icon from the step's name.** When a step is created without an `icon`, the server picks one from a fixed list of icon names by matching keywords in the step name. For example, "Vehicle Info" gets `car`, "NDA Signing" gets `file-signature`, and "Health Declaration" gets `heart-pulse`. If nothing matches, the step gets a neutral default icon, so new steps never end up with a null icon.
- **API: renaming keeps the icon in sync.** If a step is renamed and its current icon is still the one the old name would have picked (so nobody chose it by hand), the server picks a new icon from the new name. An icon an admin chose explicitly is never overwritten.
- **API: older steps with no icon get one when read.** Existing custom steps stored with `icon = null` are returned with an icon picked from their name. No data migration is needed.
- **API: the list of icon names becomes a documented contract.** The fixed list of icon names lives in one module. The React and Flutter clients use the same list.
- **Web: render the right glyph for every icon name.** `StepCard.tsx` gets a correct mapping for every icon name in the list. New SVG icons are added to `components/icons.tsx` (car, briefcase/package, id-card, camera, heart-pulse, file-signature, laptop, and so on). An icon name the web app doesn't know falls back to a neutral icon, not the pencil.
- **Web: separate drag-handle icon.** `SortableStepCard.tsx` uses a dotted grip icon for its drag handle, so it no longer looks like a second step icon.
- Not breaking: `icon` on create and update stays optional and accepts any string up to 50 characters, as it does today. Clients that send an icon behave exactly as before.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `form-builder`: new requirements for how a registration step gets its icon. They cover the fixed list of icon names, picking an icon from the step's name on create, re-picking it on rename, filling in an icon when an older step has none, and how the admin UI shows each icon name. The spec has no requirement about step icons today.

## Impact

- **VMSS_API**: a new `src/vmss_api/form_builder/step_icons.py` holding the icon-name list and the matching logic. `service.py` (`create_step`, `update_step`, and the step serialisers, including the effective-form payload) and `router.py` (`icon=step.icon`) are updated. `defaults.py` keeps its seeded icon names, now checked against the list. New tests go in `form_builder` tests. `docs/features/form-builder.md` documents the icon-name list.
- **VMMS_WEB**: changes to `presentation/components/icons.tsx` (new glyphs), `admin-form-builder/Components/StepCard.tsx` (icon-name mapping and fallback), and `Components/SortableStepCard.tsx` (grip icon for the drag handle). `CreateStepModal`, the use cases, and the repositories are not changed, because the server picks the icon.
- **API contract**: there is no schema change and no migration. The `icon` field on the response is now always filled in (it can still be `null` in the schema).
- **Flutter**: if it shows step icons, it should map the same icon names. That's a heads-up only; no change is required here.
