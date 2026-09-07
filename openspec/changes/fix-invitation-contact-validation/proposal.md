## Why

Running the backend's invitation-creation test suite (`src/vmss_api/invitations/tests.py`, 231 tests, VMSS_API repo) confirms the `POST /invitations` and `POST /registrations/walk-in` contracts already work correctly end to end, and explicitly support a visitor who supplies only an email **or** only a phone number (`_require_reachable_contact`/`_require_contact_for_method` in `invitations/schemas.py`, and the reschedule/SMS test at `tests.py:4575` using `primary_contact_email=None`). The web app's own specs agree: `staff-visitor-registration`'s "Primary contact details are required" requirement and `visitor-request-wizard`'s "Visitor Info step requires core contact and address details" requirement both currently say the system SHALL require full name, email, **and** phone together — stricter than the API they submit to.

Reading the actual wizard code (`use-staff-visitor-registration-wizard.ts`, `use-visitor-request-wizard.ts`, `AddVisitorForm.tsx`, `VisitorFieldsForm.tsx`) shows the implementation matches that stricter spec: it hard-requires both `email` and `phone` for the primary contact and every added visitor, in both the staff-created-invitation wizard and the visitor self-service wizard. A visitor who only has a phone number (or only an email) can never get past step 1, even though the API they're submitting to was built to accept exactly that. This is very likely the "validation error" being seen on the web when creating an invitation.

A second, related defect surfaced in the same code: both wizards also hard-require a "Profile Image" upload before the Visitor Info step can be completed, but neither wizard's submission code (`HttpStaffVisitRequestRepository.submit`, `HttpVisitRequestRepository.submit`) ever attaches that file to the multipart request — it's captured, previewed, and then silently dropped. The backend accepts an optional `primary_contact_photo_file`/`visitor_photo_files` upload (and `visitor-request-wizard`'s own spec documents "Photo supplied and valid is stored and returned" as a real scenario), so today's behavior forces every visitor through an extra mandatory upload step that accomplishes nothing.

## What Changes

- Relax the primary-contact and additional-visitor validation in both wizards (`staff-visitor-registration` and `visitor-request-wizard`) so at least one of email/phone satisfies the "reachable contact" requirement, matching the API contract, instead of requiring both unconditionally.
- For the primary contact specifically, require the contact field that matches the selected `preferredContactMethod` (email when "email" is chosen, phone when "sms" is chosen) rather than always requiring both regardless of the chosen method.
- Stop hard-blocking wizard progression on a missing Profile Image — make it genuinely optional in both wizards' client-side validation, matching what both specs already say ("optionally", "Optionally Captures a Profile Photo").
- Wire the captured profile image file through to the API on submission (`primaryContactPhotoFile`/matching visitor photo files) in both `HttpStaffVisitRequestRepository` and `HttpVisitRequestRepository`, so a photo the visitor does choose to add is actually persisted instead of being discarded client-side.
- Update the affected requirements in both specs to describe "at least one of email or phone, with the primary contact's choice tied to their preferred contact method" and "profile image is optional, and is transmitted to the API when supplied."

No backend (VMSS_API) changes are needed — its contract already supports all of this; only the web client's validation and submission logic are out of sync with it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `staff-visitor-registration`: "Primary contact details are required before proceeding" changes from requiring email AND phone to requiring at least one, tied to preferred contact method; "ID proof can optionally be uploaded for each visitor" gains an explicit, non-blocking profile-image upload that is actually submitted.
- `visitor-request-wizard`: "Visitor Info step requires core contact and address details" changes from requiring email AND phone to requiring at least one; "ID proof and profile image can optionally be uploaded as supporting documents" is corrected so profile image no longer blocks progression and is actually submitted with the request.

## Impact

- Affected code: `src/presentation/pages/staff-visitor-registration/hooks/use-staff-visitor-registration-wizard.ts`, `.../Components/AddVisitorForm.tsx`, `.../Components/PrimaryContactCard.tsx`; `src/presentation/pages/visitor-request/hooks/use-visitor-request-wizard.ts`, `.../Components/steps/VisitorFieldsForm.tsx`; `src/infrastructure/staff-visit-request-repository.ts`, `src/infrastructure/visit-request-repository.ts`; `src/data/repositories/visit-request-repository.ts` (the `InvitationSubmissionFiles` shape gains the optional photo fields).
- No API contract change, no VMSS_API changes, no database migration.
- Fixes real submissions being blocked today for any visitor who has only one contact channel on file, and removes a pointless mandatory upload step.
