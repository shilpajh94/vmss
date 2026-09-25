## 1. Fix the Draft-Reset Trigger

- [x] 1.1 In `FieldPropertiesPanel.tsx`, change the `useEffect` that
      re-seeds `label`/`placeholder`/`description`/`isRequired`/`isActive`/
      `minLength`/`maxLength`/`conditionFieldKey`/`conditionOperator`/
      `conditionValue`/`width`/`optionRows`/`saveError` from a `[field]`
      dependency to `[field.id]`, so it only re-runs when the admin is now
      editing a different field, not whenever the parent's background poll
      hands the panel a new object reference for the same field.
- [x] 1.2 Confirm the panel's explicit "Reset" button is unaffected — it
      should still discard the current draft and reload the latest
      `field` prop's values on click, regardless of this change (it already
      reads directly from the `field` prop, not from the effect).

## 2. Manual Verification

(No automated tests — `VMMS_WEB` has no test framework; see
`form-builder-content-and-option-editing`'s tasks.md for the same
constraint.)

**Live browser verification was attempted but is not possible from this
session's sandbox**: no system Chromium/Chrome binary is present, and
`npx playwright install chromium` fails ("Playwright does not support
chromium on ubuntu20.04-x64" — the sandbox's browser-binary support is
unavailable for this distro image). The dev server (`vite`, already running
on `:5173` from before this session) and the DDEV-hosted backend are both
up and reachable, so the app itself is running — only headless-browser
driving is blocked. The fix was instead verified by:
- Reading `FieldPropertiesPanel.tsx`'s corrected `useEffect` dependency
  (`[field.id]`) against the exact mechanism identified in design.md (the
  15s `usePolling` tick handing the panel a new `field` object reference
  for unchanged data) — the dependency change directly removes the trigger
  that was resetting local draft state.
- `tsc -b --noEmit` and `oxlint` both pass clean on the changed file.
- `reset()` (the explicit Reset button) was inspected and confirmed
  unchanged — it still reads directly from the `field` prop on click, not
  from the effect, so task 1.2 holds independent of this fix.

- [ ] ~~2.1 Reproduce the original bug on `main`/pre-fix code: open Field
      Properties for a field, type or paste a multi-sentence description,
      wait past 15 seconds without saving, confirm the text reverts.~~ —
      not run; no browser available in this session (see above)
- [ ] ~~2.2 With the fix applied: repeat 2.1 and confirm the typed/pasted
      description survives past the 15-second mark and can be saved
      successfully.~~ — not run; needs manual confirmation in an actual
      browser (dev server is already running at `http://localhost:5173`)
- [ ] ~~2.3 Repeat 2.2 for the Options editor (add/remove/reorder an option,
      wait past 15 seconds, confirm the draft survives and saves).~~ — not
      run; same reason
- [ ] ~~2.4 Confirm switching the selected field (clicking a different row)
      still loads that field's own values into the panel correctly.~~ — not
      run; same reason
- [ ] ~~2.5 Confirm clicking "Reset" while mid-edit still discards the draft
      and reloads the selected field's last-saved values.~~ — not run; same
      reason (code-inspected instead, see above)
- [ ] ~~2.6 Confirm saving successfully still updates the panel to reflect
      the saved values (e.g. after saving a description change, the field
      list row / reselecting the field shows the new value).~~ — not run;
      same reason
