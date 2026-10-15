## 1. API: icon vocabulary and inference (VMSS_API)

- [x] 1.1 Create `src/vmss_api/form_builder/step_icons.py` with `STEP_ICON_VOCABULARY`, `DEFAULT_STEP_ICON = "clipboard-list"`, the ordered `_ICON_RULES` table from design.md §1, and pure `infer_step_icon(name)` / `resolve_step_icon(icon, name)` functions (tokenise on non-alphanumerics, prefix match, exact match for keywords ≤3 chars, first rule wins)
- [x] 1.2 Unit tests for `infer_step_icon`: every spec scenario ("Vehicle Info"→`car`, "VEHICLES"→`car`, "NDA Signing"→`file-signature`, "Health Declaration"→`heart-pulse`, "Laptop Declaration"→`laptop`, "Miscellaneous"→`clipboard-list`) plus ordering guards ("Visitor Info"→`user`, "Visit Details"→`calendar`, "Consent Agreement"→`shield-check`, "Carried Items"→`briefcase`, "Idle Time" does not match `id-card`)
- [x] 1.3 Test that every `DEFAULT_STEP_SPECS` icon and every `_ICON_RULES` target is a member of `STEP_ICON_VOCABULARY`

## 2. API: wire inference into the step lifecycle

- [x] 2.1 `service.py::create_step` — persist `resolve_step_icon(payload.icon or None, payload.name)`
- [x] 2.2 `service.py::update_step` — when `name` changes and `icon` is not in the payload, re-derive the icon iff the current icon is null or equals `infer_step_icon(old_name)` (design.md §2)
- [x] 2.3 `router.py::_step_out` and `service.py::_step_to_snapshot` — serialise `resolve_step_icon(step.icon, step.name)`
- [x] 2.4 Locate where `/effective` serves a stored published snapshot and apply `resolve_step_icon` to each step dict whose `icon` is null
- [x] 2.5 Endpoint tests (httpx): create without icon → inferred icon; create with explicit icon → honoured; rename of auto-iconed step → re-derived; rename of explicitly-iconed step → unchanged; rename with icon in same PATCH → sent icon; legacy row with null icon is listed with a derived icon; `/effective` from a snapshot containing `icon: null` returns a derived icon
- [x] 2.6 Permission-denied case for create step still rejects (no regression) and a tenant-isolation case confirming inference runs against the tenant-bound session only (reuse existing form-builder fixtures)

## 3. API: docs and checks

- [x] 3.1 Document the icon vocabulary, inference behaviour, and rename rule in `docs/features/form_builder.md`
- [x] 3.2 `ruff check`, `ruff format --check`, `mypy` on `form_builder`, and `ddev exec uv run pytest src/vmss_api/form_builder` all green

## 4. Web: glyphs and step-card mapping (VMMS_WEB)

- [x] 4.1 Add Lucide-style inline SVG glyphs to `src/presentation/components/icons.tsx`: `CarIcon`, `BriefcaseIcon`, `PackageIcon`, `FileSignatureIcon`, `IdCardIcon`, `CameraIcon`, `HeartPulseIcon`, `LaptopIcon`, `AlertTriangleIcon`, `MapPinIcon`, `ClipboardListIcon`, `GripVerticalIcon`
- [x] 4.2 Create `src/presentation/pages/admin-form-builder/step-icons.ts` mapping every vocabulary slug to its glyph (reusing existing `UserIcon`, `CalendarIcon`, `ShieldIcon`, `CheckIcon`, `FileTextIcon`, `PhoneIcon`, `BuildingIcon`, `UsersIcon`, `ClockIcon`), with a comment pointing to `docs/features/form_builder.md` as the source of the vocabulary and `ClipboardListIcon` as fallback
- [x] 4.3 `Components/StepCard.tsx` — replace the local `STEP_ICONS` map and `PencilIcon` fallback with the shared mapping
- [x] 4.4 `Components/SortableStepCard.tsx` — switch the drag handle from `GridIcon` to `GripVerticalIcon`
- [x] 4.5 Web lint/typecheck/tests green (do not run prettier — see repo convention)

## 5. End-to-end verification

- [x] 5.1 In the running app, confirm default steps show user / calendar / briefcase / car / shield / check glyphs and the drag handle is a grip, not a grid
- [x] 5.2 Create steps "NDA Signing", "Health Declaration", and "Miscellaneous" via Create Registration Step and confirm each shows the expected glyph without any icon input
