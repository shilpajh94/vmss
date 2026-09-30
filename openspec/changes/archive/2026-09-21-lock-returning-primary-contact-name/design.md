## Context

See proposal.md - Why. Three existing pieces of frontend/backend state matter here:

1. `VisitorRequestWizardInitialData.primaryContact` (`src/presentation/pages/visitor-request/hooks/use-visitor-request-wizard.ts`) already carries `fullName` (among other fields) only when the visitor is a returning visitor with a non-null prefill profile — a first-time visitor's initial data never includes it. This is exactly the signal needed to know when the API will treat the primary contact as a known identity.
2. **Verified against the backend source** (`VMMS_API/src/vmss_api/invitations/schemas.py`): the create response for both `POST /invitations` and `POST /registrations/walk-in` is `InvitationOut` (the latter as an alias, `WalkInRegistrationOut`), and it carries no primary-contact field at all — just `id`, `trackingId`, `registrationType`, `source`, `status`, `visitorCategoryId`, `hostId`, `poc*`, `expiresAt`, `submittedAt`, `approvedAt`, `currentApprovalStep`. `VisitRequestResponseSchema` (`src/domain/entities/visit-request-schema.ts`) correctly reflects this narrow shape today — there is nothing to add to it; the original plan to extend it with `primaryContactFullName` is not viable, because the backend never puts that field there.
3. The backend's public, unauthenticated tracking lookup — `GET /invitations/track?trackingId=` (`InvitationTrackingOut`, `primary_contact_full_name: str`, non-null) — already has a full frontend path: `HttpVisitTrackingRepository.lookup(trackingId)` → `TrackVisitRequestUseCase.execute(trackingId)`, exposed on `AppDependencies` as `trackVisitRequestUseCase`, currently consumed only by the visitor-track-request capability. Being public and keyed only by `trackingId` (which every successful create response already returns), it's callable from both the unauthenticated visitor wizard and the authenticated staff wizard without any new backend work.

## Goals / Non-Goals

**Goals:**
- Stop the self-service wizard from letting a returning visitor type a full-name edit that the server will silently discard.
- Give both wizards a way to show the server's actual recorded name after submission, since that's the only reliable signal for staff (no pre-submit lookup) and a safety net for the visitor wizard.

**Non-Goals:**
- No pre-submit lookup for the staff wizard — the proposal/spec explicitly accepts that staff can't know ahead of submission whether a match will occur.
- No change to email/phone editability. The backend's phone-only-match behavior (carrying forward email) is already mirrored today by the existing returning-visitor prefill (email is already pre-filled into the same field the match would use), so as long as that prefilled email isn't cleared, submission naturally follows the email-match path with a consistent result. Locking email/phone is out of scope; only full name is called out by the proposal.
- No change to ID proof, photo, visit category, visit details, carried items, vehicles, consents, or co-visitor handling.

## Decisions

### Decision 1: Derive the "locked" state from the presence of a pre-filled `fullName`, not a new explicit flag
`VisitorRequestWizardInitialData.primaryContact?.fullName` is already only ever populated for a returning visitor (see the existing comment in `use-visitor-request-wizard.ts`). Reusing that presence check (captured once into form state, e.g. a `primaryContactNameLocked: boolean` computed at `buildInitialFormState` time and carried in `VisitRequestFormState`) avoids adding a second source of truth that could drift from the prefill data itself.
- **Alternative considered**: pass an explicit `isReturningVisitor` boolean through the initial data. Rejected as redundant — the prefilled name's presence already means exactly that, and every other prefilled field derives from the same "returning visitor" condition without its own flag.

### Decision 2: Render the lock as a read-only `TextField`, not a disabled one
`VisitorFieldsForm.tsx`'s "Full Name" `TextField` gains a `readOnly` prop (new, since `TextField` currently has no read-only mode) shown with a muted style and a short helper note ("Name on file — contact support to change it") rather than `disabled`, so the value remains visibly legible and still submits as part of the form payload (a `disabled` input's value can be excluded from some form-serialization paths and reads as more strongly "unavailable" than "fixed").
- **Alternative considered**: omit the field entirely for a locked primary contact and just show the name as static text. Rejected — keeping the same field type/position avoids a layout shift between first-time and returning visitors and keeps the existing validation code path (`validateVisitorContact`) unchanged, since the field is still a real form value.

### Decision 3: After a successful create, look up the confirmed name via the existing public tracking-lookup use case, not the create response
Since the create response can't carry `primaryContactFullName` (Context point 2), both `use-visitor-request-wizard.ts` and `use-staff-visitor-registration-wizard.ts` call `trackVisitRequestUseCase.execute(trackingId)` (already on `AppDependencies`) immediately after `setTrackingId(response.trackingId)`, store the result's `primaryContactFullName` in a new `confirmedFullName` state, and pass it into the shared `ReviewConfirmStep` as a new prop rendered next to the tracking id. The lookup runs after the success screen is already showing the tracking id — `confirmedFullName` starts `undefined` and fills in once the lookup resolves, rather than blocking the success transition on a second network call.
- **Alternative considered**: extend the create response schema directly. Rejected — confirmed impossible without a backend change (Context point 2).
- **Alternative considered**: re-fetch via the authenticated `GET /invitations/:id` (`InvitationDetailOut`, which does carry `primaryContactFullName`). Rejected — that endpoint requires `get_current_user` (an authenticated employee session with `invitations:view`), which the anonymous visitor wizard never has; the tracking lookup is public and already the pattern the visitor-track-request capability was built on.
- Extend `InvitationTrackOutSchema` and `TrackingLookupResponseSchema` (`src/domain/entities/invitation-track-out-schema.ts`, `tracking-lookup-response-schema.ts`) with `primaryContactFullName: z.string().min(1)`, and thread it through `toTrackingLookupResponse` in `src/infrastructure/visit-tracking-repository.ts` — the smallest change that makes the field available to `TrackVisitRequestUseCase.execute`'s existing return type.

## Risks / Trade-offs

- **[Risk] The follow-up tracking-lookup call can fail or be slow independently of the create call that already succeeded.** Mitigation: treat it as best-effort — swallow a lookup failure (leave `confirmedFullName` unset) rather than surfacing a second error state on an already-successful submission; the success screen still shows the tracking id regardless of whether the name lookup resolves.
- **[Trade-off] There's a brief window where the success screen shows the tracking id but not yet the confirmed name**, since the lookup is a second round trip after the create call. Acceptable — the confirmed name is a safety-net/informational addition, not something submission correctness depends on.
- **[Trade-off] The lock is derived from local prefill state, not re-verified against the server at submit time.** If a visitor's session is prefilled as "returning" but something changes server-side between prefill and submission (unlikely in a single wizard session), the UI still shows the field as locked while the server's behavior is what actually governs the persisted value — acceptable since the confirmation-screen lookup (Decision 3) is exactly the fallback for any such mismatch.

## Migration Plan

No data migration. Frontend-only change, released as a normal deploy. No backend change is required: the tracking-lookup endpoint and its `primaryContactFullName` field already exist and are already used elsewhere (`visitor-track-request`); this change only starts calling it from two more places.
