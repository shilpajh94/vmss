## Context

`admin-form-builder-step-editor.tsx` renders a two-column grid (`lg:grid-cols-[2fr_1fr]`) inside its own `overflow-y-auto` region: field list, then `FieldPropertiesPanel`. Below `lg` the panel is stacked under the whole list. `selectField` in `use-admin-form-builder-step-editor.ts` only sets `selectedFieldId`; the same state is also auto-set on load (`current ?? sortedFields[0]`).

## Goals / Non-Goals

**Goals:** make the panel visible after an explicit Edit click, without scrolling on initial load.

**Non-Goals:** changing layout (sticky/side-drawer/modal panel), group card editing (edited inline already), other admin pages.

## Decisions

- **Ref + scrollIntoView on explicit select.** Attach a ref to a wrapper around `FieldPropertiesPanel`; the editor's Edit handler calls `selectField` then scrolls the wrapper into view (`behavior: 'smooth'`, `block: 'start'`). Scrolling is triggered from the click handler (not an effect on `selectedFieldId`), which naturally excludes the auto-selection on load.
- **Scroll after render.** The panel already exists when re-editing another field; on first selection it mounts on the same commit, so scroll in `requestAnimationFrame` (or a `useEffect` keyed on a "scroll request" counter) to ensure the node exists.
- `block: 'start'` (not `nearest`): the panel is ~1000px tall, taller than the editor's scroll area, so `nearest` left it untouched whenever any part overlapped the view (verified in a browser on wide layout).
- Alternatives: sticky panel (doesn't fix stacked narrow layout, bigger visual change); modal (larger redesign); effect on `selectedFieldId` (would scroll on load).

## Risks / Trade-offs

- [Panel taller than viewport, `nearest` did nothing] → resolved by using `block: 'start'`.
- [Reduced-motion users] → respect `prefers-reduced-motion` by using `behavior: 'auto'`.
