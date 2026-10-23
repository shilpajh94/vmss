## 1. Shared dropdown foundation

- [x] 1.1 Extract `use-dropdown-panel` hook (open/close, outside pointerdown incl. portal panel, Esc/Tab, active index, arrows/Home/End/typeahead) under `src/presentation/hooks/`
- [x] 1.2 Migrate `MultiSelectFilter` to the hook with no visual or behaviour change
- [x] 1.3 Build `ui/SelectDropdown.tsx` with `filter` and `field` trigger variants, check-mark selected row, ARIA listbox semantics
- [x] 1.4 Add portal + fixed positioning with scroll/resize tracking and flip-up/limited-height behaviour; Esc must not close a parent modal

## 2. Adopt in shared components

- [x] 2.1 Rewrite `DropdownFilter` on `SelectDropdown` (same props; covers dashboard branch, calendar toolbar, audit filters)
- [x] 2.2 Rewrite `SelectField` on `SelectDropdown` keeping label, required marker, error border/text, disabled, `placeholderSelectable`, `labelClassName`
- [x] 2.3 Replace raw `<select>` in `DelegateInvitationModal` (incl. loading/disabled placeholder states) and `SortableFieldRow` ("Assign to group")

## 3. Verify

- [x] 3.1 Grep `src` for remaining `<select` and fix leftovers; update tests/e2e that used native select APIs
- [ ] 3.2 Manually check: dashboard branch picker (matches the screenshot case), calendar and audit filters, a modal select near the bottom, visitor wizard selects, form builder, disabled and error states, keyboard use, mobile width, light and dark theme
- [x] 3.3 Run lint, type-check and unit tests
