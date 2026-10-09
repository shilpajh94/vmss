## 1. Fix

- [x] 1.1 In `VisitorFieldsForm.tsx`, change the custom-fields wrapper's `col-span-2` to `col-span-full`.
- [x] 1.2 In `VisitorInfoModal.tsx`, change the three `col-span-2` entries (lines ~314, ~321, ~366) to `col-span-full`.

## 2. Guards

- [x] 2.1 Add `scripts/check-grid-spans.mjs` (design.md Decision 2) and chain it into `npm run lint` after `check-brand.mjs`. Confirm it fails on the original code and passes after 1.x.
- [x] 2.2 Extend `scripts/screenshot-pages.py` with the phone-width implicit-grid-column check (design.md Decision 3), which fails the run on a hit.

## 3. Verify

- [x] 3.1 At 375px, render the Visitor Info step with the Terms & Conditions custom field, and the Visitor Info modal (a one-off Playwright script in the Playwright image; the wizard behind OTP gets its OTP from Mailpit). Confirm single-column stacking. At 768px, confirm the two-column layout is unchanged.
- [x] 3.2 Run `npm run screenshots` (no failures), then `npm run build` and `npm run lint`.
