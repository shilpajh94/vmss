## Context

See proposal.md for the root-cause trace. In short: `use-visitor-request-wizard.ts`'s `validateVisitorContact` (added by `fix-invitation-contact-validation`, still open) requires `contact.preferredContactMethod` to be set for the primary contact before it will check email/phone at all, but `createEmptyVisitorFormEntry()` never seeds that field, and `VisitorFieldsForm.tsx` never surfaces `errors?.preferredContactMethod` anywhere — so the block is both real and invisible.

## Goals / Non-Goals

**Goals:**
- Make a fresh visitor-request wizard session immediately satisfy the preferred-contact-method requirement without the visitor having to touch that control, consistent with what the UI already visually implies (the toggle displays "Email" selected by default via `?? 'email'`).
- Ensure any future validation error tied to preferred contact method is visible, so this class of "silently dead Next button" bug can't recur for this field.

**Non-Goals:**
- No change to the underlying contact-requirement rules themselves (those were correct in the prior change; only the default value and error visibility were missing).
- No broader audit of every other field for the same "error set but never rendered" failure mode — this fix is scoped to the field that's actually broken today. (Worth a follow-up audit, but not blocking this fix.)

## Decisions

- **Default at data-construction time, not at validation time**: set `preferredContactMethod: 'email'` directly in `createEmptyVisitorFormEntry()`, the same place the staff wizard already does it in `createEmptyStaffVisitorFormEntry()`. Alternative considered: leave the empty-entry constructor alone and instead have `validateVisitorContact` treat a missing value as implicitly `'email'` (`contact.preferredContactMethod ?? 'email'`). Rejected because it leaves the form *state* inconsistent with what's displayed and submitted — `toVisitor()` maps `preferredContactMethod: entry.preferredContactMethod` verbatim, so an untouched entry would still submit `undefined` over the wire (the backend defaults it server-side, but that's relying on a second, separate default matching the client's display default rather than just keeping one source of truth on the client).
- **Add the missing error prop rather than removing the requirement's dependency on it**: keep `validateVisitorContact`'s existing check as-is (it's correct once the default fix lands) and just wire `error={errors?.preferredContactMethod}` into the `SegmentedToggle` block in `VisitorFieldsForm.tsx`, rendered the same way other field errors are (a `<p className="text-caption text-danger">` line), so this is consistent with every other field in the same form rather than a one-off pattern.

## Risks / Trade-offs

- [Risk] This is the second change touching the exact same requirement/file pair as the still-open `fix-invitation-contact-validation`. Applying them out of order, or archiving one without the other, could leave the spec's main copy in an inconsistent intermediate state. → Mitigation: this change's spec delta is written as the complete, final requirement text (a superset of the other change's delta), and the proposal explicitly calls out that the two should be applied and archived together.
- [Risk] None expected in the staff-created-invitation wizard — it already had this default, so it isn't affected by either the original bug or this fix.
