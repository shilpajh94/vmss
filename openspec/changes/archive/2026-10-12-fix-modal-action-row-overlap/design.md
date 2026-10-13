## Context

`Modal.tsx` renders one scroll container (`overflow-y-auto`, padding
`p-4` / `sm:p-6`, `gap-5` between children). Inside it, two rows are
`position: sticky`:

- **Title row**: `sticky -top-4 sm:-top-6` with matching negative margins.
  The negative offset cancels the container's padding, so the row pins
  flush to the container's top edge.
- **Action row** (by convention the last child, matched by
  `[&>*:last-child:has(>button)]`): `sticky bottom-0` with
  `-mx-4 -mb-4` / `sm:-mx-6 sm:-mb-6`.

A sticky element's offset is measured from the scroll container's
padding-inset edge, not its border edge. The negative bottom margin
pulls the action row down into the container's bottom padding. With
`bottom-0`, the sticky constraint then pushes the row back up by a full
padding-width: 16px on phone, 24px from `sm` up. This happens on every
render, not only while scrolling. At `sm`+ that shift exceeds the 20px
`gap-5`, so the row's opaque `bg-surface` covers the bottom of whatever
comes before it. That is the clipped Step Name input in the screenshot.
On phone the 16px shift is smaller than the gap, so it is less visible,
but the bottom spacing still collapses.

## Goals / Non-Goals

**Goals:**
- Pinned action row sits flush with the dialog's bottom edge, with the
  normal gap above it, whether or not the body scrolls.
- One fix in the shared component, so every modal is corrected.

**Non-Goals:**
- Redesigning modal layout, spacing, or the header/footer convention.
- Changing individual modals' markup.

## Decisions

- **Mirror the title row's approach: use `-bottom-4` / `sm:-bottom-6` in
  place of `bottom-0` on the action row.** This cancels the padding the
  same way the title row's `-top-*` does, so both rows follow one rule
  and the fix is a two-class change.
  - *Alternative*: move padding off the scroll container onto an inner
    body wrapper, with header and footer outside the scroll area. This is
    cleaner structurally, but it changes the DOM every modal relies on
    (the `last-child:has(>button)` convention), so it carries more risk
    than this bug needs.
  - *Alternative*: drop `-mb-*`. That leaves a padding-sized gap under
    the action row, so it doesn't reach the bottom edge, and the scrolling
    body would show below it.

## Risks / Trade-offs

- [Some modal relies on the current overlap for its look] → Check every
  `Modal` consumer listed in proposal.md at desktop and 375px. Short
  modals and long scrolling ones (`AddFieldModal`, `VisitorInfoModal`,
  `EditInvitationModal`) are the cases to watch.
- [The repo has no automated visual or Modal test, so a regression would
  surface only in manual review] → Accepted for a CSS-only fix; the
  manual checklist in tasks.md covers it.
