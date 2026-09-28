## 1. Show the Description Preview on Each Row

- [x] 1.1 In `SortableFieldRow.tsx`, render `field.helpText` via
      `ExpandableText` beneath the existing label/field-type-badge line,
      inside the row's card.
- [x] 1.2 Confirm a field with no `helpText` renders identically to today
      (no extra spacing/wrapper) — `ExpandableText` already returns `null`
      for empty/`null` text, so this should require no extra conditional.
      Implementation note: the label/badge line had to move from a single
      `flex-1` button into a `flex-col` wrapper div (button + `ExpandableText`
      as siblings), since `ExpandableText` renders its own "See more" button
      and nesting a `<button>` inside the row's original selectable `<button>`
      would have been invalid HTML. The button keeps `w-full` (and the
      wrapper `min-w-0`) so the full-row click target and text wrapping are
      unchanged from before.

## 2. Manual Verification

(No automated tests — `VMMS_WEB` has no test framework; see
`form-builder-content-and-option-editing`'s tasks.md for the same
constraint.)

**Live browser verification was attempted but is not possible from this
session's sandbox** — same constraint hit during `fix-field-properties-
panel-poll-reset`'s apply: no system Chromium/Chrome binary, and
`npx playwright install chromium` is unsupported on this distro image. The
dev server (`vite`, already running on `:5173` from before this session,
unaffected by this change) is up and serving 200s, so the app itself is
reachable — only headless-browser driving is blocked. Verified instead by:
- `tsc -b --noEmit` and `oxlint` both pass clean on `SortableFieldRow.tsx`.
- Structural review: `ExpandableText`'s own "See more" `<button>` is a
  sibling of the row's selectable label/badge `<button>`, not nested
  inside it — the original structure would have produced invalid nested
  `<button>` HTML once `ExpandableText` was added, which was caught and
  fixed during implementation (see task 1.2's note).
- The wrapper div uses `min-w-0` + the label button keeps `w-full`, so the
  flex-row layout constraints that made text wrap correctly (rather than
  overflow) and kept the click target full-width are preserved — verified
  by reasoning through the flexbox rules, not by seeing it rendered.

- [ ] ~~2.1 Open a step with a field that has a description set (e.g. the
      reported Carried Items case); confirm the row now shows a truncated
      preview.~~ — not run; no browser available in this session (see above)
- [ ] ~~2.2 Confirm "See more"/"See less" on the row preview works the same
      way it does on the visitor-facing form.~~ — not run; needs manual
      confirmation in an actual browser (dev server is already running at
      `http://localhost:5173`)
- [ ] ~~2.3 Confirm a field with no description shows an unchanged row (no
      empty gap, no layout shift versus before this change).~~ — not run;
      same reason
- [ ] ~~2.4 Confirm the row's existing drag handle, lock icon, Required
      toggle, and edit/delete buttons are all still usable with the
      preview present (no overlap/click-target regression).~~ — not run;
      same reason
