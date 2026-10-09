## Why

On a phone, the visitor request wizard's Visitor Info step packs its fields
two per row, when they should stack one per row:
- the left column is squeezed to a few characters wide, so "Full Name" wraps
  onto three lines;
- the inputs show "Full n" and "Phon";
- the Email/SMS toggle is clipped;
- the "Upload ID" drop zone is a narrow sliver.

The page doesn't scroll sideways, so the screenshot check didn't flag it.

The cause is in `VisitorFieldsForm.tsx:181`. The form's grid is
`grid-cols-1 sm:grid-cols-2`, but the admin custom-fields wrapper inside it
uses a bare `col-span-2`. In a one-column grid, an item spanning two
columns makes CSS create an implicit second column. The whole grid then
auto-places into two content-sized tracks at every width below `sm`.

This was dormant until the last change. The wrapper renders only when the
step has admin-authored fields, and "Terms & Conditions", restored as a
consent checkbox by `heal-stale-form-config-data`, is the first one on
this tenant's Visitor Info step.

The staff **Visitor Info modal** (`VisitorInfoModal.tsx:314`, `:321`,
`:366`) has the same bare `col-span-2` inside `grid-cols-1 sm:grid-cols-2`
detail grids. Its visit details, visitor contact and additional notes
sections pack two-up on a phone in the same way.

## What Changes

- Replace each bare `col-span-2` in a responsive grid with `col-span-full`.
  That spans every existing column without creating new ones: one column on
  a phone, the full row from `sm`. There are 4 occurrences: 1 in
  `VisitorFieldsForm.tsx` and 3 in `VisitorInfoModal.tsx`.
- Add a guard so this can't come back unnoticed:
  - `scripts/check-grid-spans.mjs`, chained into `npm run lint` like
    `check-brand.mjs`, fails on a breakpoint-less `col-span-<n>` (n ≥ 2)
    in `src/`. `col-span-full`, prefixed spans (`sm:col-span-2`) and an
    explicit `// grid-span-ok` opt-out on the same line are allowed.
  - `scripts/screenshot-pages.py` also fails when a CSS grid on the page
    lays out more columns than it declares, which is the signature of an
    implicit track.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `visitor-request-wizard`: its fields stack in a single column below the
  `sm` breakpoint, including when the step has admin-authored custom fields.
- `staff-dashboard`: the Visitor Info modal's detail sections stack in a
  single column below `sm`.

## Impact

- `pages/visitor-request/Components/steps/VisitorFieldsForm.tsx` and
  `components/invitation-board/VisitorInfoModal.tsx`: class-only changes.
- New `scripts/check-grid-spans.mjs`, plus a `package.json` `lint` script
  addition.
- `scripts/screenshot-pages.py` gains the implicit-column check.
- No API change and no new dependency.
