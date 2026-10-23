## 1. Tokens and base styles

- [x] 1.1 In `src/styles/theme.css`, add `--color-surface-inset` (`#ffffff`
      in `@theme`, `#1e293b` in the `[data-theme="dark"]` override), with a
      comment pointing at design.md D2 ("controls placed on a card; `bg` is
      the page canvas only").
- [x] 1.2 In the dark override, change `--color-primary` from `#e2e8f0` to
      `#22d3ee` (design.md D4). Leave `--color-on-primary` at `#0f172a`.
- [x] 1.3 In `src/styles/index.css` `@layer base`, add the `option, optgroup`
      rule that sets `background-color: var(--color-surface)` and
      `color: var(--color-text)` (design.md D1).

## 2. Native dropdowns

- [x] 2.1 `components/ui/DropdownFilter.tsx`: change the `<select>`'s
      `bg-transparent` to `bg-surface`.
- [x] 2.2 Check the other selects (`SelectField`, `SegmentedToggle` phone
      select, `DelegateInvitationModal`, form-builder `FieldPropertiesPanel`
      / `SortableFieldRow`) already set an opaque background. Fix any that
      don't.

## 3. Card insets (`bg-bg` misuse)

- [x] 3.1 Move to `bg-surface-inset`:
      - `EmptyState` icon circle;
      - `RepeatableFieldGroup` thead, sticky Actions `th`, and item panel;
      - `ExportInvitationsModal` summary box;
      - both `VisitorInfoModal` panels;
      - `StepCard` icon tile;
      - `GroupCard` and `SortableFieldRow` pills;
      - the locked rows in `admin-form-builder-step-editor.tsx`.
- [x] 3.2 Move the bordered buttons on cards to `bg-surface`: `StepCard`
      "Edit Fields" and the `FieldPropertiesPanel` secondary button.
- [x] 3.3 `ExportInvitationsButton`: change `hover:bg-bg` to
      `hover:bg-surface-muted`.
- [x] 3.4 Confirm the remaining `bg-bg` uses are page canvas only:
      `AppShell`, `PublicLayout`, `not-found`, `route-error`, and the
      `ResponsiveBoard` sticky tab strip.

## 4. Register Visitor wizard

- [x] 4.1 In `staff-visitor-registration.tsx`, change the footer bar from
      `bg-surface` to `bg-bg`, with a `/* page-canvas */` marker on that line
      (design.md D3/D6).
- [x] 4.2 Add `dark:border-border-strong dark:text-text` to the Cancel button
      so its dark outline is quiet. The light classes stay as they are.

## 5. Contrast fixes

- [x] 5.1 In `components/StepMarker.tsx`, change the unreached state from
      `bg-border text-text-muted` to `bg-border text-text-secondary`.
- [x] 5.2 In `NotificationBell.tsx`, make the same change to the zero-count
      badge.

## 6. Guards

- [x] 6.1 Extend `scripts/check-theme-colors.mjs` with the `bg-bg` rule: allow
      it in a `CANVAS_FILES` allowlist or on a line with `page-canvas`, and
      fail elsewhere with a message pointing to `surface-inset` / `surface`.
      Update the header comment. Run `npm run lint` and confirm it passes.
- [x] 6.2 Add `tests/unit/theme-tokens.test.ts`. It parses `theme.css` and
      asserts, in both themes:
      - `on-primary` on `primary` ≥ 4.5:1;
      - `text-secondary` on `border` ≥ 4.5:1;
      - `text` on `surface-inset` ≥ 4.5:1;
      - dark `surface-inset` is lighter than dark `surface`;
      - light `surface-inset` equals light `surface`.
      Run only this test file (`node --import ./scripts/unit-test-loader.mjs
      --test tests/unit/theme-tokens.test.ts`).
- [x] 6.3 Add `scripts/dark-theme-audit.py` and an `audit:dark` npm script,
      using the same Docker/Playwright invocation as `screenshots`. It forces
      dark mode via the `vmss.themeMode` localStorage key, screenshots the
      staff/admin route list into `screenshots.local/dark/`, and reports
      sub-AA text. It exits non-zero on any `<select>` with a transparent
      computed background. `--switch` adds the live-switch-vs-fresh-load
      colour diff.

## 7. Verification

- [x] 7.1 Run `npm run audit:dark` (and `--switch`) against the dev server.
      Expect: zero transparent selects, zero diffs on the switch, and no
      sub-AA findings beyond the known sidebar-active item and the
      Individual-pill false positive.
- [ ] 7.2 Manually, on Chrome/Edge (Windows) in dark, open the "All
      statuses" filter on `/staff/invitations`, Country on
      `/admin/branches/new`, and the dashboard branch picker. All option
      lists should be dark and readable. Repeat once in Firefox.
- [ ] 7.3 Manually in dark, check that:
      - `/admin/form-builder` cards show no dark holes;
      - the `/staff/visitors/new` footer shows no band, Next is cyan, and
        Cancel has a soft outline;
      - Visitor Info and Export modals show lifted (not sunken) panels;
      - the date/time pickers in the Edit/Reschedule/Export modals show a
        dark picker icon and popup.
- [ ] 7.4 Light-theme regression: run `npm run screenshots` and compare
      `/staff/visitors/new`, `/admin/form-builder` and `/staff/invitations`
      with screenshots from before the change. They should be identical
      apart from the stepper numbers and the bell's zero count.
- [x] 7.5 Run `npm run build` (type check) and `npm run lint`. Both should
      be clean.
