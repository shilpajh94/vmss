## 1. Verify backend response contract

- [x] 1.1 Confirmed against the backend source (`VMMS_API/src/vmss_api/invitations/schemas.py` `InvitationOut`, aliased as `WalkInRegistrationOut`) that **neither** `POST /invitations` nor `POST /registrations/walk-in` returns `primaryContactFullName` (or any primary-contact field) on their create response — `InvitationOut` only carries `id`, `trackingId`, `registrationType`, `source`, `status`, `visitorCategoryId`, `hostId`, `poc*`, `expiresAt`, `submittedAt`, `approvedAt`, `currentApprovalStep`. Design.md Decision 3 (extend `VisitRequestResponseSchema`) is not viable as written. **Paused — see conversation for the revised approach before continuing to task 2.1.**

## 2. Domain: tracking-lookup schema carries the confirmed name

- [x] 2.1 Add `primaryContactFullName: z.string().min(1)` to `InvitationTrackOutSchema` in `src/domain/entities/invitation-track-out-schema.ts` (backend's `InvitationTrackingOut.primary_contact_full_name`).
- [x] 2.2 Add `primaryContactFullName: z.string().min(1)` to `TrackingLookupResponseSchema` in `src/domain/entities/tracking-lookup-response-schema.ts`.
- [x] 2.3 In `toTrackingLookupResponse` (`src/infrastructure/visit-tracking-repository.ts`), map `invitationOut.primaryContactFullName` through to the returned `TrackingLookupResponse`.

## 3. Visitor wizard: lock state and field

- [x] 3.1 In `src/presentation/pages/visitor-request/hooks/use-visitor-request-wizard.ts`, derive a `primaryContactNameLocked` boolean from whether `initial?.primaryContact?.fullName` was present when the initial form state was built, and carry it in the hook's returned state (or `VisitRequestFormState`) for the Visitor Info step to read.
- [x] 3.2 Add a `readOnly` prop to `TextField` (`src/presentation/components/ui/TextField.tsx`), rendering the input non-editable with a visibly muted style, distinct from `disabled`.
- [x] 3.3 In `VisitorFieldsForm.tsx`, thread a `fullNameLocked` prop through to the "Full Name" `TextField`, setting `readOnly` and a short helper note ("Name on file for this contact") only for the primary contact when locked; additional group visitors never receive this prop as true.
- [x] 3.4 In `VisitorInfoStep.tsx` (or wherever `VisitorFieldsForm` is invoked for the primary contact vs. additional visitors), pass `fullNameLocked={primaryContactNameLocked}` only on the primary contact's instance.

## 4. Visitor wizard: confirmed name on success

- [x] 4.1 In `use-visitor-request-wizard.ts`, destructure `trackVisitRequestUseCase` from `useAppDependencies()`. Add a `confirmedFullName` state; after `setTrackingId(response.trackingId)` on a successful submit, call `trackVisitRequestUseCase.execute(response.trackingId)` and set `confirmedFullName` from its `primaryContactFullName` on success, swallowing any lookup failure (leave it unset) rather than surfacing a second error. Expose `confirmedFullName` from the hook.
- [x] 4.2 Add a `confirmedFullName?: string` prop to `ReviewConfirmStep` (`src/presentation/pages/visitor-request/Components/steps/ReviewConfirmStep.tsx`) and render it on the success screen next to the tracking id (e.g. "Registered as: <name>") only when present.
- [x] 4.3 Pass `confirmedFullName` into `ReviewConfirmStep` from the visitor request page component.

## 5. Staff wizard: confirmed name on success

- [x] 5.1 In `use-staff-visitor-registration-wizard.ts`, destructure `trackVisitRequestUseCase` from `useAppDependencies()`. Add a `confirmedFullName` state populated the same way as task 4.1, after the existing `setTrackingId(response.trackingId)` call; also clear it in `reset()`. Expose it from the hook.
- [x] 5.2 Pass `confirmedFullName` into the shared `ReviewConfirmStep` from `staff-visitor-registration.tsx`.

## 6. Verification

- [x] 6.1 **Skipped by user decision** — no running backend with seeded data available in this session to OTP-verify as a returning visitor and confirm the read-only "Full Name" field/editable co-visitor field live. Verified statically instead: type-check + production build pass, and the lock wiring (`primaryContactNameLocked` → `fullNameLocked` → `TextField`'s `readOnly`) was traced through the primary-contact-only code path.
- [x] 6.2 **Skipped by user decision** — same reasoning as 6.1; the first-time-visitor (no-prefill) path was verified by code inspection (`primaryContactNameLocked` is `false` whenever `initial?.primaryContact?.fullName` is absent), not a live OTP run.
- [x] 6.3 **Skipped by user decision** — same reasoning as 6.1; the confirmed-name lookup call and its wiring into both `ReviewConfirmStep` success screens were verified by code inspection and the successful build, not a live submission against a backend with a matching prior invitation.
- [x] 6.4 Synced this change's deltas into `openspec/specs/visitor-request-wizard/spec.md` and `openspec/specs/staff-visitor-registration/spec.md` (validated with `openspec validate --specs --strict`, 30/30 passed); archiving now.
