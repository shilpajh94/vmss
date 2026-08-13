## Context

`src/data/api/api-endpoints.ts` is currently `{} as const`, `ApiClient.makeRequest` only sends JSON bodies, and `data/repositories/`, `data/use-cases/`, `src/infrastructure/`, and `src/domain/entities/` are all empty scaffolding (`.gitkeep` only) — this is the first feature to populate them. `VITE_API_BASE_URL` is already configured (`http://localhost:8080/api/v1`) but no backend exists yet at that address. `src/presentation/components/ui/` is likewise empty and waiting for shared primitives. See `proposal.md` for why this ships now and the earlier session decisions it carries forward (real API contract, real upload endpoint, not a mock adapter).

Source: Figma file `jXdJ0LuzcPY9YxgrnqXle6`, frames `5:51`/`3:375` (Visitor Info, group/individual), `3:540` (Visit Info), `3:639` (Carried Items), `3:733` (Vehicle Info), `3:816` (Consent). Step 6 "Review & Confirm" is not in the Figma file — see proposal.md. Address, profile image, location, and building fields were requested in addition to what Figma shows and are treated exactly like the other fields in the same steps (same required/optional and validation pattern).

## Goals / Non-Goals

**Goals:**
- One coherent wizard: a single page owns step index + full form state; each step is a presentational component driven by that state.
- Real backend contract defined now (endpoints + Zod schemas), even though the server doesn't exist yet — submission will fail against a real network error until a backend is stood up, which is expected and handled (see "Submission failure" requirement).
- Shared form primitives created now, because all 6 steps need them within this same change — this is immediate reuse, not speculative.

**Non-Goals:**
- Implementing the `/visitor/track` page or wiring the returned tracking reference to it — separate, later change.
- Persisting in-progress wizard state across a page reload (e.g. to `sessionStorage`) — out of scope; a reload restarts the wizard.
- Server-side implementation of the two new endpoints — this change defines the contract the frontend calls; standing up a matching backend is not part of this repo's frontend change.

## Decisions

### Domain model
New Zod schemas under `src/domain/entities/`:
- `VisitorSchema` — `fullName`, `email`, `phone`, `address`, `visitorCategory`, `idProofType`, `idProofFileRef?`, `profileImageFileRef?` (the two file refs are upload-response references, not raw files — see Upload decision below).
- `VehicleSchema` — `vehicleType` (`"2-wheeler" | "4-wheeler" | "heavy"`), `licensePlate`, `makeModel`, `color`.
- `VisitRequestSchema` — `registrationType` (`"individual" | "group"`), `primaryContact: VisitorSchema`, `additionalVisitors: VisitorSchema[]` (empty for individual), `visitInfo: { purpose, hostNameOrEmail, preferredDate, preferredTime, expectedDuration, location, building, department, notes? }`, `carriedItems: { categories: string[], description? }`, `vehicles: VehicleSchema[]`, `consent: { agreedTerms, agreedDataUse, agreedSafety }` (all `true` when submitted, enforced client-side before submit is even attempted).
- `VisitRequestResponseSchema` — `trackingId`, `status`, `submittedAt`.
- `UploadResponseSchema` — `fileRef` (opaque string the backend can later resolve to the stored file).

### API contract
Two new `API_ENDPOINTS` entries: `CREATE_VISIT_REQUEST` (`POST /visit-requests`, `hasToken: false` — this is a public visitor-facing submission, no session) and `UPLOAD_VISITOR_DOCUMENT` (`POST /uploads/visitor-documents`, `hasToken: false`). One upload endpoint is reused for both ID proof and profile image — they're both "attach a file, get back a reference" operations with identical constraints (PNG/JPG/PDF, 5MB), so a second near-identical endpoint would add no behavioral distinction worth the duplication.

**Alternative considered**: separate `UPLOAD_ID_PROOF` and `UPLOAD_PROFILE_IMAGE` endpoints. Rejected — same request/response shape, same constraints; a single endpoint with the file as the only payload is simpler and the caller doesn't need the server to know *why* a file was uploaded until the surrounding `VisitRequest` is submitted.

### Extending `ApiClient` for multipart uploads
Add a second public method, `uploadFile({ endpointConfig, file, parserSchema })`, to the existing `ApiClient` class (same file, `src/data/api/api-client.ts`) rather than a separate client. It builds a `FormData` body and omits the `Content-Type` header (the browser sets the multipart boundary), but otherwise reuses the same base-URL/token/schema-validation logic as `makeRequest`. This keeps "all HTTP goes through `ApiClient`" intact — `data-api-layer.md` didn't anticipate multipart, but the rule's intent (single HTTP gateway, no scattered `fetch`) is served by extending the same class rather than bypassing it.

**Alternative considered**: reuse `makeRequest` by having callers pass a `FormData` as `body` and skip `JSON.stringify`. Rejected — `makeRequest`'s header logic unconditionally sets `Content-Type: application/json`, which is wrong for multipart and would require conditional logic that muddies a currently-simple method; a dedicated method keeps both simple.

### File upload sequencing
Each visitor's ID-proof/profile-image `<input type="file">` uploads immediately on file selection (via `UploadIdDocumentUseCase`/the shared upload use case), storing the returned `fileRef` in that visitor's form-state entry — not deferred to final submit. This matches the requirement that a rejected file (wrong type/too large) is reported immediately, not at the end of the wizard, and means the final `CREATE_VISIT_REQUEST` call is pure JSON with file references already resolved.

**Alternative considered**: hold raw `File` objects in form state and upload everything at final submit. Rejected — one failed upload among several would surface at the worst possible time (after the visitor has already reviewed and confirmed), and per-file validation (type/size) is clearer as an immediate per-field result.

### Step 6 "Review & Confirm" (not in Figma)
A read-only summary grouped by step (Visitor Info / Visit Info / Carried Items / Vehicle Info / Consent), a "Back" button, and a "Submit Request" button. Submitting shows a loading state, then either the confirmation (tracking ID) or an error banner that keeps the visitor on this step with all data intact (per the spec's failure requirement). No link to `/visitor/track` — that route doesn't exist yet (see Non-Goals).

### Shared form primitives now, not later
`src/presentation/components/ui/`: `TextField`, `SelectField`, `TextareaField`, `Checkbox`, `FileUploadField`, `SegmentedToggle` (used for Individual/Group and for vehicle type). Unlike the landing page's header/footer (deferred until a second consumer existed), all 6 steps in *this same change* need these primitives — the reuse is immediate, not speculative, so building them shared from the start is the correct call per the project's own YAGNI framing.

### Page structure
- `src/presentation/pages/visitor-request/visitor-request.tsx` — owns `currentStep` and the full `VisitRequestFormState`, renders the step sidebar + active step.
- `src/presentation/pages/visitor-request/hooks/use-visitor-request-wizard.ts` — step navigation, per-step validation gating "Next", and the final submit (via `useAppDependencies()`).
- `src/presentation/pages/visitor-request/Components/steps/*` — one component per step (`VisitorInfoStep`, `VisitInfoStep`, `CarriedItemsStep`, `VehicleInfoStep`, `ConsentStep`, `ReviewConfirmStep`), each a controlled view over a slice of the shared form state.
- Header reuses the same logo/wordmark markup as the landing page's `PortalHeader`, plus a back chevron that navigates to `/`. Given this is now the second consumer of that visual pattern, this change promotes it to `src/presentation/components/PortalHeader.tsx` (shared, with an optional back-chevron prop) rather than duplicating it a second time — the deferral from the landing-page change was explicitly until "a second consumer actually exists," and it now does.

## Risks / Trade-offs

- **Backend doesn't exist yet** → Every submit and every file upload will fail with a network/connection error until a backend implementing these two endpoints is stood up. Mitigation: this is expected per the earlier decision to define the contract now; the "submission failure" requirement specifically covers this so the UI degrades correctly rather than crashing.
- **Immediate-upload sequencing creates orphaned files if the visitor abandons the wizard** → a visitor who uploads a document then never submits leaves an unreferenced file on the backend. Mitigation: this is a backend lifecycle/cleanup concern (e.g. a TTL on unreferenced uploads), not addressable from the frontend; noted for whoever builds the backend.
- **Large, single-page change (6 steps + new data layer + shared UI primitives)** → higher review surface than prior changes. Mitigation: tasks.md sequences it so each layer (domain → data/infra → shared UI → steps → wiring) is independently verifiable.

## Migration Plan

1. Domain schemas → API endpoints → `ApiClient.uploadFile` → repository port/adapter → use cases → composition root wiring.
2. Shared UI primitives.
3. Promote `PortalHeader` to shared; add the back-chevron prop.
4. Step components, then the wizard page and hook wiring them together.
5. Register `/visitor/request` in `src/App.tsx`.
6. No data migration, no feature flag — this is new, additive functionality behind a previously-dead route.
