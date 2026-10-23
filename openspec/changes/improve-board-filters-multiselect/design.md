## Context

`BoardFilterBar` (shared by the staff dashboard and admin Invitations) renders four `DropdownFilter`s: a native `<select>` styled as a pill. The open menu is the OS/browser menu and holds one value. Filter state lives in `use-invitations-board.ts` as four strings (`'all'`/`''` = unfiltered) and flows into `columnQuery` → `usePagedBoardColumns`, which runs one `GET /invitations` per status column. The backend (`invitations/router.py`) takes a single `str` for `purposeOfVisit`, `registrationType`, `source` and `status`. `DropdownFilter` is also used by the calendar toolbar, audit filter bar and branch dashboard, which must not change.

## Goals / Non-Goals

**Goals:** polished themed multi-select dropdown; OR-within / AND-across filter semantics; exact per-column totals; no backend change; accessible.

**Non-Goals:** changing other pages' dropdowns; backend multi-value params; multi-value export files; persisting filters across sessions.

## Decisions

1. **New `MultiSelectFilter` component** in `components/ui/` (not a mode of `DropdownFilter`), so the three other consumers stay untouched. Props: `icon`, `options`, `values: string[]`, `onChange(values)`, `allLabel`, `ariaLabel`. Trigger is a `button` (`aria-haspopup="listbox"`, `aria-expanded`), panel is an absolutely positioned `role="listbox" aria-multiselectable` with `role="option"` rows holding a custom checkbox, Tailwind v4 theme tokens (`border-border-strong`, `bg-surface`, `text-text`, admin accent for checked, soft shadow). Opening/closing via click, Esc, outside `pointerdown`, arrow-key navigation, Space/Enter toggles. Panel is `fixed`/portal-free but z-indexed above sticky column headers; on `max-sm` it takes the trigger's full width. Summary: none → `allLabel`; one → its label; many → `"<first> +N"`. Selecting all options is normalised to empty ("all").

2. **State as arrays.** `purposeFilter`, `registrationTypeFilter`, `statusFilter`, `sourceFilter` become `string[]` (empty = unfiltered); the `'all'` sentinel is dropped. `?status=` seeds `[value]` if valid. `isFiltering`/`clearFilters` use `length > 0`. `BoardExtraFilter` gains `values`/`onChange(values)`; `purposeOptions` and the `*_FILTER_OPTIONS` "All …" pseudo-options go away (the "All" label is the trigger's `allLabel`).

3. **Status multi-select = more visible columns.** `visibleStatuses` maps each selected API status to its board status; empty → all. `focusClosedStatus` picks the first selected closed status (checked-out/denied/archived) so the Closed column opens on one the user chose.

4. **Fan-out for purpose / type / source, merge client-side.** `ColumnQuery` carries arrays. For each column the hook builds the cartesian product of the selected values (an empty dimension contributes one "unset" entry) and issues one request per combination. Because a visit request has exactly one purpose, type and source, combinations are disjoint, so **`total` = sum of the combos' totals** (exact) and merging needs only an id dedupe and a rank-interleave. Single-valued selections degenerate to today's one request per column. `fetchWindow`/`loadMore` apply the same fan-out: page *n* is requested for every combo at the same depth, results merged by interleaving rank (the list payload doesn't expose `status_changed_at`, so combinations can't be sorted against each other). Known limitation: while paging, a newer row from a combo's page *n+1* can land above rows already shown from another combo's page *n*; accepted. A combination cap (48 per column) guards request volume: beyond it the hook falls back to treating the largest dimension as unfiltered and the UI shows a toast-level hint — in practice purposes (6, each queried as label and slug = 12) × types (2) × sources (2) = 48 worst case, so the cap is rarely hit and only when nearly everything is selected.

   *Alternative rejected:* extending the API to accept repeated params — exact paging but blocked on backend work; the user chose frontend-only fan-out.

5. **Export stays single-valued.** `GET /invitations/export` also takes one value per filter and returns a binary file that cannot be merged client-side. `exportFilterSummary` lists all selected values; if any of purpose/type/source/status has more than one value, the Export dialog shows an inline note ("Export supports one value per filter — narrow … to export") and disables the Export action. Single selections export exactly as today.

6. **Layout.** Triggers keep the 200px width on `sm+` and full width on mobile; bar wrapping rules in `BoardFilterBar` are unchanged.

## Risks / Trade-offs

- More requests per refresh/poll when many values are ticked → cap + only combos for visible columns; polling already re-queries per column.
- Approximate ordering across pages (Decision 4) → documented; totals stay exact.
- Disabling export for multi-values may surprise users → explicit inline explanation.
- Custom dropdown a11y regressions vs native select → keyboard + ARIA covered in tasks and tested.

## Addendum: purpose stored as label or slug

Invitations hold `purposeOfVisit` as either the display label ("Interview") or the option slug ("interview"), and the backend matches exactly. Each selected purpose is therefore queried under both spellings (extra disjoint combinations). Export still sends the single selected label only, so a purpose export can miss slug-stored rows until the backend matches case-insensitively.
