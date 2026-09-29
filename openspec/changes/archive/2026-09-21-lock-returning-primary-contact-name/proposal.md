## Why

The invitation-creation API now looks up the submitted primary contact by email (or, when no email is submitted, by phone) against every prior invitation regardless of status. When it finds a match, it silently overwrites `primaryContactFullName` (and, for a phone-only match, `primaryContactEmail` too) with the name/email on file, ignoring whatever the form submitted — there is no error, no validation message, just a different value in the response than what was sent. Today neither wizard renders the create response's name back to the user, and the self-service wizard's "Full Name" field stays freely editable even for a visitor whose identity the OTP-verified prefill already resolved, so a returning visitor can type a new name, submit, and have it discarded without any indication that happened.

## What Changes

- In the visitor request wizard, the primary contact's "Full Name" field becomes read-only whenever it was pre-filled from a returning visitor's OTP-verified profile (visitor-return-history's prefill), since the server will silently discard any edit to it. First-time visitors (no prefill) and every additional group visitor are unaffected and keep a normal editable field — the lock never applies to co-visitors.
- The shared create response (`POST /registrations/walk-in` and `POST /invitations`, identical contract) does not carry the primary contact's name at all, so after a successful submission both wizards make a follow-up call to the existing public tracking-lookup endpoint (already used by the visitor-track-request capability) with the returned tracking reference, and the submission confirmation screen (shared by the visitor wizard and the staff registration wizard) displays that lookup's primary contact name as the confirmed name on record, instead of assuming the submitted value stuck.
- The staff registration wizard has no pre-submit lookup to detect a returning contact ahead of time, so it relies entirely on the confirmation screen's tracking lookup to reveal when the backend corrected a name the staff member typed.
- No change to phone, ID proof, photo, visit category, visit details, carried items, vehicles, consents, or co-visitor handling — all remain freely editable and submitted fresh, matching the backend's unchanged behavior for those fields.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `visitor-request-wizard`: the primary contact's "Full Name" field is read-only when pre-filled from a returning visitor's profile; the submission confirmation shows the create response's `primaryContactFullName` as the confirmed name of record.
- `staff-visitor-registration`: the submission confirmation shows the create response's `primaryContactFullName` as the confirmed name of record, since staff has no pre-submit way to know the typed name will be overwritten.

## Impact

- `src/domain/entities/invitation-track-out-schema.ts`, `src/domain/entities/tracking-lookup-response-schema.ts`: add `primaryContactFullName`, threaded through `toTrackingLookupResponse` in `src/infrastructure/visit-tracking-repository.ts` — no change to `VisitRequestResponseSchema` (the create response genuinely has no primary-contact field to add).
- `src/presentation/pages/visitor-request/hooks/use-visitor-request-wizard.ts`: after a successful submit, call the existing `trackVisitRequestUseCase` with the returned tracking id to populate a `confirmedFullName` state; the "returning visitor" prefill already available on `VisitorRequestWizardInitialData.primaryContact` needs a flag (or the presence of a prefilled `fullName`) exposed to the Visitor Info step to drive the read-only state.
- `src/presentation/pages/staff-visitor-registration/hooks/use-staff-visitor-registration-wizard.ts`: same follow-up `trackVisitRequestUseCase` call and `confirmedFullName` state after a successful submit.
- `src/presentation/pages/visitor-request/Components/steps/VisitorFieldsForm.tsx` / `VisitorInfoStep.tsx`: render the primary contact's "Full Name" `TextField` as read-only when locked, with a short explanatory note.
- `src/presentation/pages/visitor-request/Components/steps/ReviewConfirmStep.tsx` (shared by both wizards): show `confirmedFullName` on the success screen once the lookup resolves.
