## 1. Fix the default value

- [x] 1.1 In `createEmptyVisitorFormEntry()` (`src/presentation/pages/visitor-request/types.ts`), add `preferredContactMethod: 'email'` to the returned object, matching `createEmptyStaffVisitorFormEntry()`'s existing convention.

## 2. Surface the error visibly

- [x] 2.1 In `VisitorFieldsForm.tsx`'s "Preferred Contact Method" block (the `showContactMethod &&` section), pass `error={errors?.preferredContactMethod}` into (or alongside) the `SegmentedToggle`, and render it as a `<p className="text-caption text-danger">` line the same way every other field in this form displays its error.

## 3. Verification

- [ ] 3.1 Reload the visitor self-service wizard from a completely fresh session (no pre-filled state), fill in only the fields that were required before this fix (full name, email, address, visitor category, ID proof type/file), and confirm "Next" now advances past the Visitor Info step without touching the Preferred Contact Method toggle.
- [ ] 3.2 Manually clear/break the preferred contact method in a way that fails validation (if reachable through the UI) and confirm an error message now appears next to the control instead of Next silently doing nothing.
- [ ] 3.3 Re-run the scenarios from `fix-invitation-contact-validation`'s own verification tasks (4.1–4.4) that this bug blocked, now that Next is unblocked.
- [x] 3.4 Run `npm run lint` and `npx tsc -b`. (Both clean.)
