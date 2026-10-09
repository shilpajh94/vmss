## 1. Domain and prefill wiring

- [x] 1.1 Add `idProofUrl` (nullish) to `VisitorPrefillSchema` in `src/domain/entities/visitor-portal-schema.ts`, matching the existing `photoUrl` field.
- [x] 1.2 In `src/presentation/pages/visitor-request/visitor-request.tsx`, update `buildPrimaryContactPrefill` (and its stale "never includes an ID-proof image or profile photo" comment) to carry `idProofUrl`/`photoUrl` through from `prefill` into the wizard's initial data.
- [x] 1.3 Extend `VisitorRequestWizardInitialData['primaryContact']` in `src/presentation/pages/visitor-request/hooks/use-visitor-request-wizard.ts` to include the existing ID-proof/photo URLs, and update its comment to reflect that these are now conditionally prefilled.

## 2. Existing-file state and fetch-to-File resolution

- [x] 2.1 ~~Add per-field existing-file state...~~ Simplified during implementation: `idProofFileRef`/`profileImageFileRef` being set (or not) on `formState.primaryContact` *is* the ready/not-ready state — `FileUploadField` already renders "empty" vs. "has a file" purely from those refs, so a separate status enum would just duplicate that. No `keep` flag needed either: keeping is simply "the ref stays set," replacing is "the ref changes."
- [x] 2.2 On mount, when initial data includes an existing URL for a field, eagerly `fetch()` it, convert the response to a `File` (extension inferred from `Content-Type`, falling back to `.bin`), and register it into the existing `fileRegistry` via `uploadFile()` — so `idProofFileRef`/`profileImageFileRef` point at a real, submit-ready file without changing `submit()`. Implemented as two small `useEffect`s in `use-visitor-request-wizard.ts` plus a module-level `fetchExistingFile` helper.
- [x] 2.3 On fetch failure (network error, non-2xx, CORS failure), the `.catch()` is a no-op — `idProofFileRef`/`profileImageFileRef` stay unset, so the field falls back to the normal fresh-upload control (design.md Decision 3).
- [ ] 2.4 Verify in the target environment that the presigned file-storage URLs send CORS headers permitting a `fetch()` from the portal's origin (design.md Risks — same failure mode as the prior audit-report download CORS gap); note the outcome in the PR description. **Not verifiable from this session** (no access to the deployed/stage environment) — flag for manual check before merge.

## 3. Visitor Info step UI

- [x] 3.1 **No new rendering mode needed** — `FileUploadField` (`src/presentation/components/ui/FileUploadField.tsx`) already renders a thumbnail (image) or document icon + filename whenever `previewUrl`/`fileName` are set, for any file behind a `fileRef` — it doesn't distinguish "freshly picked" from "resolved from an existing URL." Once task 2.2 populates `idProofFileRef`/`idProofFileName` (or the profile-image equivalents), `VisitorFieldsForm.tsx` passes them straight through unchanged and the existing-file preview appears for free.
- [x] 3.2 **"Replace" is the field's existing click-to-pick-a-new-file affordance** — the whole preview is one `<label>` wrapping the hidden file input, so clicking it (whether it's showing "Click to upload" or an existing-file preview) opens the picker and, on a valid selection, calls the same `onFileRefChange` that already overwrites `idProofFileRef`/`idProofFileName`. "Keep existing" is simply not clicking it. No new prop or button added — this reuses the control's current behavior exactly as it already works for a freshly uploaded file.
- [x] 3.3 Confirmed — validation reads `contact.idProofFileRef`/`contact.profileImageFileRef` (`validateVisitorContact` in `use-visitor-request-wizard.ts`), which task 2.2 already populates; no change needed.
- [x] 3.4 Confirmed — the existing-file effects only ever write to `formState.primaryContact`; `additionalVisitors` entries are always created via `createEmptyVisitorFormEntry()` and never touched by them, so their ID-proof fields always render the plain fresh-upload control.

## 4. Review step

- [x] 4.1 Confirmed — `ReviewConfirmStep.tsx`'s `FilePreviewCell` already renders from `fileName`/`getFilePreviewUrl(fileRef)` generically, with no "no file chosen" special-casing that could misread a kept file. No change needed.

## 5. Spec sync and verification

- [ ] 5.1 Manually verify the end-to-end flow: OTP-verify as a returning visitor with a prior photo/ID-proof, confirm both show as existing-file previews, keep one and replace the other, submit, and confirm the request succeeds with the expected files.
- [ ] 5.2 Manually verify a returning visitor whose prefill profile has no `idProofUrl`/`photoUrl` (or `prefill` is null) still gets the plain fresh-upload controls, matching current behavior.
- [ ] 5.3 Run `openspec sync-specs` (or the equivalent skill) after implementation to fold this change's deltas into `openspec/specs/visitor-return-history/spec.md` and `openspec/specs/visitor-request-wizard/spec.md`, then archive the change.
