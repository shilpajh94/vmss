## Context

Both invitation-creating wizards duplicate the same validation and submission logic rather than sharing it:

- `use-staff-visitor-registration-wizard.ts` (`validateStaffVisitorContact`) and `AddVisitorForm.tsx` (`handleAdd`) — staff-created invitation flow, `POST /invitations`.
- `use-visitor-request-wizard.ts` (`validateVisitorContact`) and `VisitorFieldsForm.tsx` (shared by primary contact and group visitors, driven by the `showContactMethod` prop) — visitor self-service flow, `POST /registrations/walk-in`.

Both currently hard-require `email && phone`, and both hard-require a profile image (`profileImageFileRef`) that is captured into an in-memory `fileRegistry` but never attached to the outgoing `FormData` in `HttpStaffVisitRequestRepository.submit` / `HttpVisitRequestRepository.submit`. The backend (`VMSS_API`, not touched by this change) already accepts `primary_contact_photo_file` / `visitor_photo_files` as optional multipart fields and only requires one of email/phone (the one matching `preferredContactMethod` for the primary contact).

## Goals / Non-Goals

**Goals:**
- Bring client-side validation in both wizards down to exactly what the API requires — no more, no less.
- Make the profile-image capture actually reach the API when a visitor chooses to provide one, instead of being a dead-end UI step.
- Keep the two wizards' validation logic easy to compare/audit — this change doesn't merge them into one shared module, since they already diverge in unrelated ways (staff wizard resolves `branchId` from a selected location; visitor wizard doesn't).

**Non-Goals:**
- No backend/VMSS_API change — its contract is already correct.
- No refactor to unify the two wizards' duplicated validation code into a shared hook/utility. That's a reasonable follow-up but is a separate, larger refactor with its own risk; this change stays focused on the reported bug.
- No change to the `department_to_visit`/host fields or their spec staleness in `visitor-request-wizard` — that's already tracked by the in-flight `role-based-invitation-workflow` change.

## Decisions

- **Contact requirement, primary contact**: require exactly the field matching `preferredContactMethod` (email for "email", phone for "sms"), not "at least one of the two picked arbitrarily." This mirrors the backend's `_require_contact_for_method` exactly and avoids a confusing case where a visitor picks "SMS" as their preferred channel but the UI is satisfied by an email address alone.
- **Contact requirement, additional group visitors**: require "at least one of email or phone," with no method-matching, since group visitors don't carry a `preferredContactMethod` field in either the UI or the API (`VisitorSubmit`/`_require_reachable_contact`).
- **Profile image**: make optional in validation (`errors.profileImageFileRef` check removed from both `validateStaffVisitorContact`/`validateVisitorContact`, and the `required` prop dropped from the relevant `FileUploadField`/`InlineFileUpload` usages), and add it to `InvitationSubmissionFiles` as an optional field (`primaryContactPhotoFile?: File`) that both repositories append to `FormData` as `primary_contact_photo_file` when present. Visitor-level photo files for group members are out of scope here — neither wizard currently gives group visitors a photo upload control, so there's nothing to wire through for them.
- **Where to change validation errors**: keep validation inline in each wizard's existing `validate*Contact` function and each form's own `handleAdd`/field-level checks, rather than introducing a new shared validator — smallest diff that fixes the reported behavior without a broader refactor mid-fix.

## Risks / Trade-offs

- [Risk] A visitor who has always filled in both fields won't notice any behavior change, but a visitor who previously worked around the bug by entering a fake phone number or email just to get past validation may now have bad contact data on file from before this fix — no automated backfill is possible since the wizard doesn't mark which value was real. → Mitigation: none needed for new submissions going forward; flag to product/support as a data-quality note if it comes up, not something this change can fix retroactively.
- [Risk] Wiring the profile image into the multipart request changes what staff/visitors have been implicitly testing (a photo that used to go nowhere now persists and appears wherever `primaryContactPhotoUrl` is surfaced, e.g. `VisitorInfoModal`/badge views). → Mitigation: this is the intended, spec-documented behavior (`visitor-request-wizard`'s existing "Photo supplied and valid is stored and returned" scenario already assumed this worked); no additional guard needed beyond the existing 5MB/PNG-JPG validation already in place client-side and enforced again server-side.
