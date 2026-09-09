## Why

The still-open `fix-invitation-contact-validation` change relaxed the visitor-request wizard's primary-contact validation so only the field matching the visitor's `preferredContactMethod` is required, instead of always requiring both email and phone. That change introduced a regression: `createEmptyVisitorFormEntry()` (`src/presentation/pages/visitor-request/types.ts`) never sets a default `preferredContactMethod` on a fresh form entry — it's `undefined` until the visitor explicitly touches the "Preferred Contact Method" segmented toggle. The new `validateVisitorContact` in `use-visitor-request-wizard.ts` treats a missing `preferredContactMethod` as its own blocking error (`errors.preferredContactMethod = 'Preferred contact method is required.'`) before it even looks at email/phone. Since `VisitorFieldsForm.tsx` never renders any error text for that key — the "Preferred Contact Method" block has no `error` prop wired up at all — the block is completely invisible: the visitor sees the toggle visually showing "Email" selected (via the display-only `value.preferredContactMethod ?? 'email'` fallback) and has no reason to click it, so "Next" silently does nothing on every fresh visitor-request wizard session.

This was confirmed by re-reading the current source (`types.ts`, `use-visitor-request-wizard.ts`, `VisitorFieldsForm.tsx`) after the report that Next stops responding on the Visitor Info step of the visitor self-service wizard, with no visible error. The staff-created-invitation wizard doesn't have this bug because its equivalent `createEmptyStaffVisitorFormEntry()` already sets `preferredContactMethod: 'email'` explicitly.

## What Changes

- Default `preferredContactMethod` to `'email'` in `createEmptyVisitorFormEntry()`, matching the already-established convention in the staff wizard's `createEmptyStaffVisitorFormEntry()` and the value the toggle already displays. This makes the "missing preferred contact method" validation branch unreachable in normal use, since a fresh entry now always has one.
- As defense in depth, wire up visible error display for the "Preferred Contact Method" control in `VisitorFieldsForm.tsx` (pass and render `errors?.preferredContactMethod`), so that if this field is ever invalid for some other reason in the future, the block is visible instead of silent.
- No change to the validation rules themselves (email-for-"email", phone-for-"sms", added in the prior change) — this only fixes the default value and error visibility that made the existing rule unusable from a fresh session.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `visitor-request-wizard`: the "Visitor Info step requires core contact and address details" requirement (already modified by the still-open `fix-invitation-contact-validation` change) is refined to specify that Preferred Contact Method has a default value of "Email" for a new visitor session, and that any validation error on it is visibly displayed rather than silently blocking progression.

## Impact

- Affected code: `src/presentation/pages/visitor-request/types.ts` (`createEmptyVisitorFormEntry`), `src/presentation/pages/visitor-request/Components/steps/VisitorFieldsForm.tsx` (error display for the contact-method toggle).
- No backend change, no change to the wire contract.
- This is a regression fix for a change that has not yet been archived (`fix-invitation-contact-validation`); the two are tightly coupled and should be applied and archived together rather than independently.
