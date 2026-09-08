## 1. Shared file-submission plumbing

- [x] 1.1 Add an optional `primaryContactPhotoFile?: File` field to `InvitationSubmissionFiles` in `src/data/repositories/visit-request-repository.ts`.
- [x] 1.2 In `HttpStaffVisitRequestRepository.submit` (`src/infrastructure/staff-visit-request-repository.ts`), append `primary_contact_photo_file` to the outgoing `FormData` when `files.primaryContactPhotoFile` is present.
- [x] 1.3 In `HttpVisitRequestRepository.submit` (`src/infrastructure/visit-request-repository.ts`), append `primary_contact_photo_file` to the outgoing `FormData` when `files.primaryContactPhotoFile` is present.

## 2. Staff-created invitation wizard (`POST /invitations`)

- [x] 2.1 In `use-staff-visitor-registration-wizard.ts`'s `validateStaffVisitorContact`, replace the unconditional `!contact.email` / `!contact.phone` checks with: require the field matching `contact.preferredContactMethod` (email for "email", phone for "sms"), and drop the `!contact.profileImageFileRef` required check.
- [x] 2.2 In the same file's `submit`, pass the primary contact's captured photo file (looked up from `fileRegistry` via `profileImageFileRef`, same pattern as `primaryContactIdProofFile`) as `primaryContactPhotoFile` alongside `primaryContactIdProofFile`/`visitorIdProofFiles`.
- [x] 2.3 In `AddVisitorForm.tsx`'s `handleAdd`, replace `!draft.email || !draft.phone` with a check that at least one of the two is filled in (keep the phone-format validation only when a phone number is actually supplied).
- [x] 2.4 Update `PrimaryContactCard.tsx` / `VisitorFieldsForm.tsx` (`showContactMethod` path) so the Email and Phone fields are no longer marked `required` unconditionally — reflect that only the field matching the selected preferred contact method is mandatory, and remove `required` from the Profile Image upload for the primary contact.
- [x] 2.5 Update `AddVisitorForm.tsx`'s Email/Phone fields so neither is marked `required` on its own (validation still enforces "at least one" via 2.3).

## 3. Visitor self-service wizard (`POST /registrations/walk-in`)

- [x] 3.1 In `use-visitor-request-wizard.ts`'s `validateVisitorContact`, replace the unconditional `!contact.email` / `!contact.phone` checks with: for the primary contact, require the field matching `preferredContactMethod`; for additional visitors, require at least one of email or phone. Drop the `!contact.profileImageFileRef` required check.
- [x] 3.1b (found during implementation, not in original breakdown) `VisitorInfoStep.tsx`'s `commitDraft` has its own separate, identical "email && phone both required" check for the group "Add Visitor" draft — fixed the same way as 3.1's additional-visitor case.
- [x] 3.2 In the same file's `submit`, pass the primary contact's captured photo file as `primaryContactPhotoFile` alongside `primaryContactIdProofFile`/`visitorIdProofFiles`.
- [x] 3.3 Update `VisitorFieldsForm.tsx` so the Email/Phone fields are not both marked `required` (drive `required` off which field matches `preferredContactMethod` when `showContactMethod` is true, and off nothing extra — validation-only — when it's false for group visitors), and remove `required` from the Profile Image field when `showExtendedFields` is true.

## 4. Verification

- [ ] 4.1 Manually exercise the staff wizard end to end with a primary contact that has only a phone number and "SMS" selected as preferred contact method; confirm it reaches the Review step and submits successfully.
- [ ] 4.2 Manually exercise the visitor self-service wizard the same way (phone-only, SMS preferred), plus a group visitor with only an email address.
- [ ] 4.3 Confirm a profile image attached in either wizard actually appears on the resulting invitation (e.g. via the staff invitation-board detail view) after submission.
- [ ] 4.4 Confirm submitting with no profile image at all still succeeds in both wizards.
- [x] 4.5 Run the project's lint/typecheck and any existing wizard-related component/unit tests. (`npm run lint` and `npx tsc -b` both clean; no component/unit test suite exists in this project yet — see `package.json` scripts.)
