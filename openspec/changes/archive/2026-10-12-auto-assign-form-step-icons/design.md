## Context

- `FormStep.icon` (`form_builder/models.py`) is a nullable `String(50)`. `FormStepCreate` and `FormStepUpdate` accept any string up to 50 characters. `defaults.py` seeds six steps with `user`, `calendar`, `briefcase`, `car`, `shield-check`, and `check-circle`.
- `create_step` (`service.py`) stores `payload.icon` exactly as sent. The web `CreateStepModal` collects only a name, and `use-admin-form-builder.ts::createStep` sends `{ key, name }`, so every custom step ends up with `icon = null`.
- A step's icon is serialised in two places: `router.py::_step_out` (the admin step endpoints and `/effective`) and `service.py::_step_to_snapshot` (the published snapshot JSON).
- On the web, `StepCard.tsx` has a six-entry `STEP_ICONS` map that sends `car` to `GridIcon` and `briefcase` to `FileTextIcon`, and falls back to `PencilIcon`. `SortableStepCard.tsx` draws its drag handle with the same `GridIcon`, so "Vehicle Info" shows two grids. The icons are custom inline SVGs in `components/icons.tsx` (Lucide-style 24×24 strokes). There is no icon library dependency.

## Goals / Non-Goals

**Goals:**
- The server is the single source of truth for a step's icon, so the React portal and the Flutter app agree without each re-implementing the matching logic.
- No schema change, no migration, and no change to the request or response contract.

**Non-Goals:**
- An icon picker in the Create or Edit Step UI. The server picks an icon automatically, and choosing one by hand stays API-only for now.
- Icons in the visitor-facing wizard (`StepProgressHeader`), which doesn't show step icons today.
- Rejecting icon names outside the list on write. That would tighten validation on an existing field, which `api-conventions.md` §2 counts as a breaking change.
- Picking icons with ML or fuzzy matching. A keyword table is predictable, easy to test, and easy to extend.

## Decisions

### 1. Keyword table in a new `form_builder/step_icons.py`
The module holds three things:
- `STEP_ICON_VOCABULARY: frozenset[str]`
- `DEFAULT_STEP_ICON = "clipboard-list"`
- An ordered `_ICON_RULES: list[tuple[str, tuple[str, ...]]]` that maps each icon name to its keywords

It also exposes two pure functions:
- `infer_step_icon(name: str) -> str`
- `resolve_step_icon(icon: str | None, name: str) -> str`, which returns `icon` when it is set and otherwise falls back to `infer_step_icon(name)`

How matching works: lowercase the name, split it into words on anything that isn't a letter or digit, and match each word against the keywords with `word.startswith(keyword)`. A prefix match covers plurals and other word forms ("vehicles", "signing", "declaration"). The first rule in the list that matches wins. The order goes from the most specific step type to the most generic, so "Visitor Vehicle Info" gets `car` before the more generic `user` rule can match.

Starting table (rules are checked top to bottom; the right-hand column is the step type each rule covers):

| Icon name | Keywords | Step type |
|---|---|---|
| `car` | vehicle, car, parking, bike, transport | vehicle |
| `laptop` | laptop, device, computer, asset, equipment | equipment |
| `briefcase` | carried, belonging, item, luggage, bag | carried items |
| `package` | package, parcel, deliver, courier | deliveries |
| `shield-check` | consent, privacy, security, polic, compliance, terms | consent and compliance |
| `file-signature` | nda, sign, agreement, contract, undertaking | signed agreements |
| `heart-pulse` | health, medical, covid, vaccin, symptom | health |
| `alert-triangle` | safety, emergency, hazard, induction | safety |
| `id-card` | id, identity, document, passport, kyc, proof | identity |
| `camera` | photo, camera, selfie, picture | photo |
| `phone` | contact, phone, mobile | contact details |
| `building` | company, organi, employer, business | company |
| `users` | group, accompan, companion, team | groups |
| `map-pin` | location, address, site | location |
| `clock` | time, schedule, slot, duration | timing |
| `user` | visitor, personal, guest, profile | the person |
| `calendar` | visit, appointment, meeting, date, purpose | the visit |
| `check-circle` | review, confirm, summary | review |
| `file-text` | note, form, detail, declaration | catch-all for document-style steps |

Short keywords such as `id` and `car` match whole words only, not prefixes. This avoids false positives like "**id**le" or "**car**ried". Every keyword of three characters or fewer is matched exactly.

The rule order matters, and each of these cases is pinned by a test:
- `user` comes before `calendar`, because `visit` is a prefix of `visitor`. "Visitor Info" must get `user`, and "Visit Details" must get `calendar`.
- `shield-check` comes before `file-signature`, so "Consent Agreement" gets the shield.
- Generic words such as `info` and `details` are kept out of the specific rules. They would otherwise override the word that actually describes the step.

- *Alternative: infer the icon on the web client.* Rejected. Flutter would need a second copy of the table, and the two would drift apart.
- *Alternative: store a separate `icon_is_auto` column so a rename knows whether to re-pick.* Rejected. It needs a migration, and the rule in Decision 2 gives the same behaviour without one.

### 2. Rename re-picks the icon only if it was auto-picked
In `update_step`, if `name` is in the changed fields and `icon` is not, check whether the step's current icon is null or equal to `infer_step_icon(old_name)`. If so, set it to `infer_step_icon(new_name)`. Otherwise leave it alone, because an icon that differs from what the old name would produce must have been chosen by hand. One edge case: a hand-picked icon that happens to equal the auto-picked one will be re-picked on rename. That's acceptable, because the admin's choice and the automatic choice were the same icon.

### 3. Fill in a missing icon when reading, not with a backfill migration
`_step_out` and `_step_to_snapshot` serialise `resolve_step_icon(step.icon, step.name)`. Published snapshots that already exist may still contain `"icon": null`. The code that serves `/effective` from a snapshot applies the same fill-in to each step dict. This is cheaper and safer than a data migration across every tenant schema, and it also covers rows created through the API by any client that sends no icon.

### 4. `create_step` stores the resolved icon
`icon=resolve_step_icon(payload.icon or None, payload.name)`, so new rows are never null. `defaults.py` keeps its explicit icon names. A unit test checks that each one is in the icon list.

### 5. Web: map every icon name to its own glyph, and give the drag handle its own icon
- Add the missing Lucide-style glyphs to `components/icons.tsx`: `CarIcon`, `BriefcaseIcon`, `PackageIcon`, `FileSignatureIcon`, `IdCardIcon`, `CameraIcon`, `HeartPulseIcon`, `LaptopIcon`, `AlertTriangleIcon`, `MapPinIcon`, `ClipboardListIcon`, and `GripVerticalIcon`. Reuse the glyphs that already exist (`UserIcon`, `CalendarIcon`, `ShieldIcon`, `CheckIcon`, `FileTextIcon`, `PhoneIcon`, `BuildingIcon`, `UsersIcon`, `ClockIcon`).
- Move `STEP_ICONS` into `admin-form-builder/step-icons.ts`, covering every icon name in the list, with `ClipboardListIcon` as the fallback.
- In `SortableStepCard`, change the drag handle from `GridIcon` to `GripVerticalIcon`.
- We add inline SVGs instead of a dependency such as `lucide-react`, to match the existing `icons.tsx` approach. Adding a library for about 12 glyphs isn't worth it.

## Risks / Trade-offs

- [A keyword matches the wrong step type, e.g. "Visitor Device Info" gets `laptop` when the admin meant "person"] → First-match-wins order puts the more specific step types first, which is usually what the admin means. Fixing a wrong match only takes a new keyword or a reordered rule, plus a test case.
- [Only English keywords] → Step names are admin-entered and in English today. Anything unrecognised gets the neutral default, so nothing breaks.
- [The web and API icon lists drift apart] → The web falls back to a neutral glyph for unknown names. `docs/features/form-builder.md` lists the icon names, and the web's `step-icons.ts` points to it in a comment.
- [Old published snapshots carry `icon: null`] → Decision 3 fills in the icon wherever a snapshot is served.

## Migration Plan

No database migration is needed. Deploy the API first: on its own it only fills in icon names. Then deploy the web, which renders the new names. An older web build shows the pencil for icon names it doesn't know, which is no worse than today. To roll back, revert either repo on its own.
