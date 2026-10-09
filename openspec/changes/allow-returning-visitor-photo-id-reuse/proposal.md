## Why

The returning-visitor self-service feature currently forces a visitor to re-upload their ID-proof document and profile photo on every visit, even though the backend's `GET /visitor-portal/me` lookup already returns valid, fetchable presigned URLs for both files from the visitor's most recent prior visit. Always requiring a fresh upload adds friction for a visitor a host has already seen and verified, and the "never prefill" rule was written before the backend was confirmed to expose these URLs. We now want returning visitors to see their existing photo and ID-proof document and choose to keep or replace them, instead of always starting from an empty dropzone.

## What Changes

- The visitor-portal lookup's prefill profile is no longer treated as ID-proof/photo-free: `idProofUrl` and `photoUrl`, when present, are read by the frontend instead of being dropped.
- The Visitor Info step's "Upload ID" and "Profile Image" fields, when a prefill URL is available for that field, render a thumbnail/document preview of the existing file with a "Keep existing" / "Replace" choice, instead of an empty dropzone.
- Choosing "Replace" reverts that field to the existing fresh-upload dropzone (unchanged validation: PNG/JPG/PDF for ID proof, PNG/JPG for photo, 5MB limit).
- Choosing "Keep existing" (or taking no action) carries the existing file forward as-is for that field on submission; the visitor is not required to re-upload it.
- This prefill and keep/replace behavior applies only to the primary contact of a returning visitor's new request (mirroring how the other prefill fields — name, email, phone, ID-proof type — already work); group-list visitors and first-time visitors are unaffected and keep the existing fresh-upload-only behavior.
- **BREAKING (spec)**: reverses the "ID-proof document image is never returned or prefilled" requirement in `visitor-return-history` and the corresponding "SHALL NOT pre-fill the ID-proof document image or profile photo" clause in `visitor-request-wizard`.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `visitor-return-history`: replaces the "ID-proof document image is never returned or prefilled" requirement with one requiring the ID-proof document image and profile photo to be read from the lookup's prefill profile and made available to the wizard for reuse.
- `visitor-request-wizard`: updates "Wizard is reachable from the landing page's request entry point" (drops the "SHALL NOT pre-fill the ID-proof document image or profile photo" clause and its scenario) and "ID proof and profile image can optionally be uploaded as supporting documents" (adds the keep-existing-or-replace behavior when a prefill URL is present for the primary contact).

## Impact

- `src/domain/entities/visitor-portal-schema.ts`: add `idProofUrl` to `VisitorPrefillSchema` (nullish, matching the existing `photoUrl` field).
- `src/presentation/pages/visitor-request/visitor-request.tsx`: `buildPrimaryContactPrefill` currently drops `idProofUrl`/`photoUrl` by design (see its comment) — it now needs to carry both through into the wizard's initial data.
- `src/presentation/pages/visitor-request/hooks/use-visitor-request-wizard.ts`: `VisitorRequestWizardInitialData['primaryContact']` needs `idProofUrl`/`photoUrl` fields; initial form state needs an existing-file/keep-or-replace flag per upload field instead of only `File | undefined`.
- The Visitor Info step's ID-proof and profile-photo upload components (wherever they render the dropzone) need an "existing file" preview state with Keep/Replace actions.
- Submission logic needs to send the existing file reference (or otherwise signal "no change") when the visitor keeps the prefilled file rather than replacing it, instead of assuming a `File` is always freshly selected.
